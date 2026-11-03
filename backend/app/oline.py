from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


class OlineError(Exception):
    """Erreur renvoyée par Oline / iTop."""


class Oline:
    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        version: str = "1.3",
        verify_ssl: bool | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = (url or os.environ.get("OLINE_URL", "")).strip()
        self.api_key = api_key or os.getenv("OLINE_API_KEY")  # base64 de "user:pwd"
        self.version = version
        self.timeout = timeout
        if verify_ssl is None:
            raw_verify = os.getenv("OLINE_VERIFY_SSL", "true").strip().lower()
            if raw_verify in ("false", "0", "no", "off"):
                verify_ssl = False
            elif os.path.exists(raw_verify):
                verify_ssl = raw_verify
            else:
                verify_ssl = True
        self.verify_ssl = verify_ssl

    # --------------------------------------------------------------------- #
    # --- MÉTHODES DE CRÉATION ET GESTION ---
    # --------------------------------------------------------------------- #

    def create_ticket(
        self,
        title: str,
        description: str,
        *,
        ticket_class: str = "UserRequest",  # ou "Incident"
        org_id: str | int | None = "Direction Informatique",
        caller_id: str | int | None = None,
        agent_id: str | int | None = None,
        team_id: str | int | None = None,
        service_id: str | int | None = None,
        servicesubcategory_id: str | int | None = None,
        urgency: str | int | None = None,
        impact: str | int | None = None,
        priority: str | int | None = None,
        origin: str | None = None,
        status: str | None = None,
        comment: str = "Création via API Ouverture de flux",
        output_fields: str = "id,ref,friendlyname,title,status,priority",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        fields = {
            "title": title,
            "description": description,
            "org_id": self._resolve_organization(org_id) if org_id is not None else None,
            "caller_id": self._resolve_person(caller_id) if caller_id is not None else None,
            "agent_id": self._resolve_person(agent_id) if agent_id is not None else None,
            "team_id": f"SELECT Team WHERE name ='{team_id}'" if team_id is not None else None,
            "service_id": f"SELECT Service WHERE name='{service_id}'" if service_id is not None else None,
            "servicesubcategory_id": f"SELECT ServiceSubcategory WHERE name='{servicesubcategory_id}'" if servicesubcategory_id is not None else None,
            "impact": impact,
            "urgency": urgency,
            "priority": priority,
            "origin": origin,
            "status": status,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        fields.update(extra_fields)

        body = {
            "operation": "core/create",
            "class": ticket_class,
            "comment": comment,
            "output_fields": output_fields,
            "fields": fields,
        }

        result = self._post(body)
        return next(iter(result["objects"].values()))

    def get_ticket(self, ticket_class: str, oql_query: str) -> dict[str, Any] | None:
        """Récupère un ticket unique ou ses informations via une requête OQL."""
        body = {
            "operation": "core/get",
            "class": ticket_class,
            "key": oql_query,
            "output_fields": "id,ref,status,title",
        }
        result = self._post(body)
        objects = result.get("objects", {})
        if not objects:
            return None
        return next(iter(objects.values()))

    def find_tickets(
        self,
        *,
        title: str | None = None,
        ref: str | None = None,
        caller_id: str | None = None,
        org_id: str | int | None = None,
        status: str | None = None,
        exact: bool = True,
        ticket_class: str = "UserRequest",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Recherche des tickets existants (anti-doublon après une relance)."""
        conditions = []
        if ref:
            conditions.append(f"ref = '{self._esc(ref)}'")
        if title:
            if exact:
                conditions.append(f"title = '{self._esc(title)}'")
            else:
                conditions.append(f"title LIKE '%{self._esc(title)}%'")
        if caller_id:
            conditions.append(f"caller_id->email = '{self._esc(caller_id)}'")
        if org_id is not None:
            conditions.append(f"org_id = {self._resolve_organization_id(org_id)}")
        if status:
            conditions.append(f"status = '{self._esc(status)}'")

        if not conditions:
            raise OlineError("find_tickets : au moins un critère est requis.")

        body = {
            "operation": "core/get",
            "class": ticket_class,
            "key": f"SELECT {ticket_class} WHERE " + " AND ".join(conditions),
            "output_fields": "id,ref,title,status,priority,org_name,start_date",
        }
        objects = self._post(body).get("objects") or {}
        tickets = [{"id": obj.get("key"), **obj.get("fields", {})} for obj in objects.values()]
        tickets.sort(key=lambda t: int(t["id"]) if str(t["id"]).isdigit() else 0, reverse=True)
        return tickets[:limit]

    def add_attachment(
        self,
        ticket_id: str | int,
        file_path: str | None = None,
        filename: str = "document.pdf",
        mimetype: str = "application/pdf",
        file_bytes: bytes | None = None,
        comment: str = "Document officiel PDF joint via API Ouverture de flux",
    ) -> dict[str, Any]:
        """Ajoute une pièce jointe à un ticket existant."""
        if file_bytes is not None:
            data = base64.b64encode(file_bytes).decode("utf-8")
        elif file_path:
            with open(file_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
        else:
            raise ValueError("file_path ou file_bytes est requis")

        body = {
            "operation": "core/create",
            "class": "Attachment",
            "comment": comment,
            "fields": {
                "item_class": "UserRequest",
                "item_id": ticket_id,
                "contents": {
                    "data": data,
                    "filename": filename,
                    "mimetype": mimetype,
                },
            },
        }
        return self._post(body)

    def add_comment(self, ticket_id: str | int, comment: str, is_public: bool = True) -> dict[str, Any]:
        """Ajoute un commentaire dans le journal public ou privé du ticket."""
        field = "public_log" if is_public else "private_log"
        body = {
            "operation": "core/update",
            "class": "UserRequest",
            "key": f"SELECT UserRequest WHERE id = {ticket_id}",
            "fields": {
                field: comment,
            },
        }
        return self._post(body)

    def apply_stimulus(
        self,
        ticket_id: str | int,
        stimulus: str,
        *,
        ticket_class: str = "UserRequest",
        comment: str = "Changement via API",
        output_fields: str = "id,ref,status",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        body = {
            "operation": "core/apply_stimulus",
            "class": ticket_class,
            "key": f"SELECT {ticket_class} WHERE id = {ticket_id}",
            "stimulus": stimulus,
            "comment": comment,
            "output_fields": output_fields,
            "fields": extra_fields,
        }

        result = self._post(body)
        return next(iter(result["objects"].values()))

    # --------------------------------------------------------------------- #
    # --- MÉTHODES INTERNES ET UTILITAIRES ---
    # --------------------------------------------------------------------- #

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.url:
            raise OlineError("OLINE_URL n'est pas configuré.")
        try:
            response = httpx.post(
                self.url,
                data={
                    "version": self.version,
                    "json_data": json.dumps(payload, ensure_ascii=False),
                },
                headers={"Authorization": f"Basic {self.api_key}"} if self.api_key else {},
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise OlineError(f"Connexion à Oline impossible : {exc}") from exc

        if response.status_code >= 400:
            raise OlineError(f"HTTP {response.status_code} : {response.text[:300]}")

        body = response.json()
        if body.get("code"):
            raise OlineError(f"[iTop {body['code']}] {body.get('message')}")
        return body

    @staticmethod
    def _esc(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("'", "\\'")

    def _resolve_organization_id(self, org: str | int) -> int:
        if isinstance(org, int) or str(org).strip().isdigit():
            return int(org)

        body = {
            "operation": "core/get",
            "class": "Organization",
            "key": f"SELECT Organization WHERE name = '{self._esc(str(org).strip())}'",
            "output_fields": "id,name",
        }
        objects = self._post(body).get("objects") or {}
        ids = sorted(int(obj["key"]) for obj in objects.values())
        if not ids:
            raise OlineError(f"Organisation introuvable : {org!r}")
        return ids[0]

    def _resolve_organization(self, org: str | int) -> str:
        return f"SELECT Organization WHERE id = {self._resolve_organization_id(org)}"

    def _resolve_person_id(self, person: str | int) -> int:
        if isinstance(person, int) or str(person).strip().isdigit():
            return int(person)

        body = {
            "operation": "core/get",
            "class": "Person",
            "key": f"SELECT Person WHERE email = '{self._esc(str(person).strip())}'",
            "output_fields": "id,name",
        }
        objects = self._post(body).get("objects") or {}
        ids = sorted(int(obj["key"]) for obj in objects.values())
        if not ids:
            raise OlineError(f"Personne introuvable pour l'email : {person!r}")
        return ids[0]

    def _resolve_person(self, person: str | int) -> str:
        return f"SELECT Person WHERE id = {self._resolve_person_id(person)}"

    def _get_list(self, class_name: str, oql_query: str, output_fields: str) -> list[dict[str, Any]]:
        body = {
            "operation": "core/get",
            "class": class_name,
            "key": oql_query,
            "output_fields": output_fields,
        }
        result = self._post(body)
        objects = result.get("objects")
        if isinstance(objects, dict):
            return [obj["fields"] for obj in objects.values() if "fields" in obj]
        return []

    # --- MÉTHODES DE RÉCUPÉRATION DE LISTES ---

    def get_organizations(self) -> list[str]:
        results = self._get_list("Organization", "SELECT Organization", "name")
        return sorted(list({item["name"] for item in results if item.get("name")}))

    def get_organizations_detailed(self) -> list[dict[str, Any]]:
        body = {
            "operation": "core/get",
            "class": "Organization",
            "key": "SELECT Organization",
            "output_fields": "name",
        }
        objects = self._post(body).get("objects") or {}
        orgs = [{"id": int(o["key"]), "name": o["fields"]["name"]} for o in objects.values()]
        return sorted(orgs, key=lambda o: o["id"])

    def get_person_emails(self) -> list[str]:
        results = self._get_list("Person", "SELECT Person", "email")
        return sorted(list({item["email"] for item in results if item.get("email")}))

    def get_teams(self) -> list[str]:
        results = self._get_list("Team", "SELECT Team", "name")
        return sorted(list({item["name"] for item in results if item.get("name")}))

    def get_services(self) -> list[str]:
        results = self._get_list("Service", "SELECT Service", "name")
        return sorted(list({item["name"] for item in results if item.get("name")}))

    def get_service_subcategories(self, service_name: str | None = None) -> list[str]:
        if service_name:
            query = f"SELECT ServiceSubcategory AS ss JOIN Service AS s ON ss.service_id = s.id WHERE s.name = '{service_name}'"
        else:
            query = "SELECT ServiceSubcategory"

        results = self._get_list("ServiceSubcategory", query, "name")
        return sorted(list({item["name"] for item in results if item.get("name")}))
