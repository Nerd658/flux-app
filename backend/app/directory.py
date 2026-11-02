"""Authentification par l'annuaire (Active Directory, LDAPS).

L'application ne stocke aucun mot de passe d'annuaire : elle demande a l'AD de verifier le couple
CUID / mot de passe (bind LDAP), puis lit l'identite de l'utilisateur. Les roles restent geres dans l'appli.
"""
import logging
import os
from dataclasses import dataclass

from ldap3 import NONE, SAFE_SYNC, SUBTREE, Connection, Server, ServerPool
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.config import get_settings

logger = logging.getLogger("directory")


class DirectoryUnavailable(Exception):
    """Annuaire injoignable : la connexion est refusee (fail securely), seul le compte de secours passe."""


@dataclass
class DirectoryUser:
    cuid: str
    nom: str
    prenom: str
    email: str | None
    telephone: str
    departement: str


def _first(entry, attr: str) -> str:
    value = entry[attr].value if attr in entry else None
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip() if value else ""


class ActiveDirectoryAuthentication:
    """Authentification Active Directory multi-serveurs."""

    def __init__(self):
        settings = get_settings()
        self.AD_DOMAIN = os.getenv("AD_DOMAIN") or settings.ad_domain
        timeout_env = os.getenv("AD_RESPONSE_TIMOUT") or os.getenv("AD_RESPONSE_TIMEOUT")
        self.AD_RESPONSE_TIMEOUT: int = int(timeout_env) if timeout_env else settings.ad_response_timeout
        self.AD_SERVERS_IP = os.getenv("AD_SERVERS_IP") or settings.ad_servers_ip

        if self.AD_SERVERS_IP:
            self.server_pool = ServerPool(
                Server(host.strip(), port=389, use_ssl=False, connect_timeout=self.AD_RESPONSE_TIMEOUT, get_info=NONE)
                for host in self.AD_SERVERS_IP.split(",")
                if host.strip()
            )
        else:
            self.server_pool = None

    def authenticate(self, username: str, password: str) -> bool:
        if not password or not self.server_pool or not self.AD_DOMAIN:
            return False

        bind_user = f"{self.AD_DOMAIN}\\{username}"
        try:
            conn = Connection(
                self.server_pool,
                user=bind_user,
                password=password,
                client_strategy=SAFE_SYNC,
                auto_bind=True,
            )
            ok = bool(conn.bind() or conn.bound)
            try:
                conn.unbind()
            except Exception:
                pass
            return ok
        except Exception as exc:
            logger.warning("Echec authentification AD pour %s : %s", username, exc)
            return False

    def authenticate_and_fetch(self, username: str, password: str) -> DirectoryUser | None:
        if not password or not self.server_pool or not self.AD_DOMAIN:
            return None

        bind_user = f"{self.AD_DOMAIN}\\{username}"
        conn = None
        bound = False
        try:
            conn = Connection(
                self.server_pool,
                user=bind_user,
                password=password,
                client_strategy=SAFE_SYNC,
                auto_bind=True,
            )
            bound = bool(conn.bind() or conn.bound)
        except Exception as exc:
            logger.warning("Echec connexion/bind AD pour %s : %s", username, exc)
            bound = False

        if not bound or not conn:
            return None

        # Le bind a reussi : l'utilisateur est authentifie
        nom = username
        prenom = "-"
        email = None
        telephone = ""
        departement = "Non renseignee"

        try:
            settings = get_settings()
            base_dn = settings.ldap_base_dn
            if not base_dn and self.AD_DOMAIN:
                base_dn = ",".join(f"DC={part}" for part in self.AD_DOMAIN.split("."))

            if base_dn:
                flt = (
                    f"(&(objectClass=user)({settings.ldap_cuid_attribute}={escape_filter_chars(username)})"
                    "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
                )
                conn.search(
                    base_dn,
                    flt,
                    SUBTREE,
                    attributes=[
                        "givenName",
                        "sn",
                        "displayName",
                        "name",
                        "mail",
                        "telephoneNumber",
                        "department",
                    ],
                    size_limit=1,
                )
                if conn.entries:
                    entry = conn.entries[0]
                    nom = _first(entry, "sn") or username
                    prenom = _first(entry, "givenName") or "-"
                    display_name = _first(entry, "displayName") or _first(entry, "name")

                    if (not prenom or prenom == "-") and display_name:
                        parts = display_name.split()
                        if len(parts) >= 2:
                            prenom = parts[0]
                            nom = " ".join(parts[1:])
                        else:
                            prenom = display_name

                    email = _first(entry, "mail") or None
                    telephone = _first(entry, "telephoneNumber")
                    departement = _first(entry, "department") or "Non renseignee"
        except Exception as search_exc:
            logger.debug("Recherche d'attributs AD ignoree : %s", search_exc)
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

        return DirectoryUser(
            cuid=username,
            nom=nom or username,
            prenom=prenom or "-",
            email=email,
            telephone=telephone,
            departement=departement,
        )


def ad_authenticate(cuid: str, password: str) -> DirectoryUser | None:
    """Point d'entree unifie : tente ActiveDirectoryAuthentication si configure, sinon LDAPS direct."""
    if not password:
        return None

    settings = get_settings()
    if (os.getenv("AD_SERVERS_IP") or settings.ad_servers_ip) and (os.getenv("AD_DOMAIN") or settings.ad_domain):
        ad_auth = ActiveDirectoryAuthentication()
        return ad_auth.authenticate_and_fetch(cuid, password)

    if not settings.ldap_url:
        return None

    server = Server(settings.ldap_url, use_ssl=True, get_info=NONE, connect_timeout=5)
    conn = Connection(
        server,
        user=f"{cuid}@{settings.ldap_upn_suffix}",
        password=password,
        receive_timeout=5,
        raise_exceptions=False,
    )
    try:
        if not conn.bind():
            return None
        flt = (
            f"(&(objectClass=user)({settings.ldap_cuid_attribute}={escape_filter_chars(cuid)})"
            "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        )
        conn.search(
            settings.ldap_base_dn,
            flt,
            SUBTREE,
            attributes=["givenName", "sn", "mail", "telephoneNumber", "department"],
            size_limit=1,
        )
        if not conn.entries:
            return None
        e = conn.entries[0]
        return DirectoryUser(
            cuid=cuid,
            nom=_first(e, "sn") or cuid,
            prenom=_first(e, "givenName") or "-",
            email=_first(e, "mail") or None,
            telephone=_first(e, "telephoneNumber"),
            departement=_first(e, "department") or "Non renseignee",
        )
    except LDAPException as exc:
        raise DirectoryUnavailable(str(exc)) from exc
    finally:
        conn.unbind()
