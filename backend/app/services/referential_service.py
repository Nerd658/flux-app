from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Country, Departement, Direction, FluxLine, FluxRequest, FluxType, User, Zone
from app.schemas import (
    DepartementIn,
    DepartementOut,
    DirectionOut,
    FluxRequestIn,
    LabelOut,
    LabelUsageOut,
    ManagerInfoOut,
    ReferentielsOut,
)

MAX_ITEMS_PER_LIST = 200


@dataclass(frozen=True)
class ReferentialDefinition:
    model: Any
    label: str

    def compute_usage(self, db: Session) -> dict[str, int]:
        return {}


class FluxTypeDefinition(ReferentialDefinition):
    def compute_usage(self, db: Session) -> dict[int, int]:
        stmt = select(FluxRequest.flux_type_id, func.count()).group_by(FluxRequest.flux_type_id)
        return dict(db.execute(stmt).all())


class DirectionDefinition(ReferentialDefinition):
    def compute_usage(self, db: Session) -> dict[str, int]:
        stmt = select(FluxRequest.direction, func.count()).group_by(FluxRequest.direction)
        return dict(db.execute(stmt).all())


class DepartementDefinition(ReferentialDefinition):
    def compute_usage(self, db: Session) -> dict[str, int]:
        stmt = select(FluxRequest.departement, func.count()).group_by(FluxRequest.departement)
        return dict(db.execute(stmt).all())


class PairColumnDefinition(ReferentialDefinition):
    def __init__(self, model: Any, label: str, col_src, col_dst):
        super().__init__(model, label)
        object.__setattr__(self, "col_src", col_src)
        object.__setattr__(self, "col_dst", col_dst)

    def compute_usage(self, db: Session) -> dict[str, int]:
        def group_by_col(col):
            return dict(db.execute(select(col, func.count()).group_by(col)).all())

        a = group_by_col(getattr(self, "col_src"))
        b = group_by_col(getattr(self, "col_dst"))
        return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


REFERENTIAL_REGISTRY: dict[str, ReferentialDefinition] = {
    "flux-types": FluxTypeDefinition(FluxType, "Types d'ouverture"),
    "directions": DirectionDefinition(Direction, "Directions"),
    "departements": DepartementDefinition(Departement, "Départements"),
    "zones": PairColumnDefinition(Zone, "Zones", FluxLine.src_zone, FluxLine.dst_zone),
    "pays": PairColumnDefinition(Country, "Pays", FluxLine.src_pays, FluxLine.dst_pays),
}


class ReferentialService:
    @staticmethod
    def get_definition(kind: str) -> ReferentialDefinition:
        definition = REFERENTIAL_REGISTRY.get(kind)
        if not definition:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Liste inconnue")
        return definition

    @staticmethod
    def exists_label(
        db: Session,
        model: Any,
        libelle: str,
        exclude_id: int | None = None,
        direction_id: int | None = None,
    ) -> bool:
        stmt = select(model.id).where(func.lower(model.libelle) == libelle.lower())
        if direction_id is not None and hasattr(model, "direction_id"):
            stmt = stmt.where(model.direction_id == direction_id)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        return db.scalar(stmt) is not None

    @staticmethod
    def _normalize_manager_cuid(raw: str | None) -> str | None:
        if not raw or not raw.strip():
            return None
        cuids = [c.strip().upper() for c in raw.replace(";", ",").split(",") if c.strip()]
        return ", ".join(dict.fromkeys(cuids)) if cuids else None

    @classmethod
    def _resolve_managers_map(cls, db: Session, directions: list[Direction]) -> dict[int, list[ManagerInfoOut]]:
        all_cuids = set()
        for d in directions:
            all_cuids.update(d.authorized_managers)
        if not all_cuids:
            return {}

        users = db.scalars(
            select(User).where(User.cuid.in_(all_cuids), User.is_active.is_(True))
        ).all()
        user_by_cuid = {u.cuid: u for u in users}

        result: dict[int, list[ManagerInfoOut]] = {}
        for d in directions:
            mgrs: list[ManagerInfoOut] = []
            for cuid in d.authorized_managers:
                u = user_by_cuid.get(cuid)
                if u:
                    mgrs.append(
                        ManagerInfoOut(
                            cuid=u.cuid,
                            nom=u.nom,
                            prenom=u.prenom,
                            email=u.email,
                            telephone=u.telephone,
                            role=u.role.value if hasattr(u.role, "value") else str(u.role),
                        )
                    )
                else:
                    mgrs.append(
                        ManagerInfoOut(
                            cuid=cuid,
                            nom=cuid,
                            prenom="",
                            email=f"{cuid.lower()}@orange.com",
                            telephone="",
                            role="manager",
                        )
                    )
            result[d.id] = mgrs
        return result

    @classmethod
    def list_all(cls, db: Session) -> ReferentielsOut:
        flux_types = list(db.scalars(select(FluxType).order_by(FluxType.libelle)))
        directions_db = list(db.scalars(select(Direction).order_by(Direction.libelle)))
        departements_db = list(db.scalars(select(Departement).order_by(Departement.libelle)))
        zones = list(db.scalars(select(Zone).order_by(Zone.libelle)))
        pays = list(db.scalars(select(Country).order_by(Country.libelle)))

        dir_mgr_map = cls._resolve_managers_map(db, directions_db)
        dept_mgr_map = cls._resolve_managers_map(db, departements_db)

        dir_map_by_id = {d.id: d.libelle for d in directions_db}

        departements_out = [
            DepartementOut(
                id=d.id,
                direction_id=d.direction_id,
                direction_libelle=dir_map_by_id.get(d.direction_id, ""),
                libelle=d.libelle,
                manager_cuid=d.manager_cuid,
                managers=dept_mgr_map.get(d.id, []),
            )
            for d in departements_db
        ]

        depts_by_dir_id: dict[int, list[DepartementOut]] = {}
        for dept in departements_out:
            depts_by_dir_id.setdefault(dept.direction_id, []).append(dept)

        directions_out = [
            DirectionOut(
                id=d.id,
                libelle=d.libelle,
                manager_cuid=d.manager_cuid,
                managers=dir_mgr_map.get(d.id, []),
                departements=depts_by_dir_id.get(d.id, []),
            )
            for d in directions_db
        ]

        return ReferentielsOut(
            flux_types=flux_types,
            directions=directions_out,
            departements=departements_out,
            zones=zones,
            pays=pays,
        )

    @classmethod
    def list_with_usage(cls, db: Session) -> dict[str, list[LabelUsageOut]]:
        out = {}
        for kind, definition in REFERENTIAL_REGISTRY.items():
            usage_map = definition.compute_usage(db)
            items = db.scalars(select(definition.model).order_by(definition.model.libelle)).all()
            if kind == "flux-types":
                out[kind] = [
                    LabelUsageOut(id=item.id, libelle=item.libelle, usage=usage_map.get(item.id, 0))
                    for item in items
                ]
            elif kind == "directions":
                mgr_map = cls._resolve_managers_map(db, items)
                out[kind] = [
                    LabelUsageOut(
                        id=item.id,
                        libelle=item.libelle,
                        usage=usage_map.get(item.libelle, 0),
                        manager_cuid=item.manager_cuid,
                        managers=mgr_map.get(item.id, []),
                    )
                    for item in items
                ]
            elif kind == "departements":
                mgr_map = cls._resolve_managers_map(db, items)
                dir_names = dict(db.execute(select(Direction.id, Direction.libelle)).all())
                out[kind] = [
                    LabelUsageOut(
                        id=item.id,
                        libelle=item.libelle,
                        usage=usage_map.get(item.libelle, 0),
                        manager_cuid=item.manager_cuid,
                        managers=mgr_map.get(item.id, []),
                        direction_id=item.direction_id,
                        direction_libelle=dir_names.get(item.direction_id, ""),
                    )
                    for item in items
                ]
            else:
                out[kind] = [
                    LabelUsageOut(id=item.id, libelle=item.libelle, usage=usage_map.get(item.libelle, 0))
                    for item in items
                ]
        return out

    @classmethod
    def add_label(cls, db: Session, model: Any, libelle: str, user: User, request: Request, action: str, **extra):
        direction_id = extra.get("direction_id")
        if cls.exists_label(db, model, libelle, direction_id=direction_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette valeur existe deja")
        if db.scalar(select(func.count()).select_from(model)) >= MAX_ITEMS_PER_LIST:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre maximal de valeurs atteint")

        fields = {"libelle": libelle, **extra}
        if hasattr(model, "created_by_id"):
            fields["created_by_id"] = user.id
        item = model(**fields)
        db.add(item)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette valeur existe deja") from None

        audit(
            db,
            action,
            actor_id=user.id,
            entity=model.__tablename__,
            entity_id=item.id,
            request=request,
            details={"libelle": item.libelle},
        )
        return item

    @classmethod
    def create_referential(
        cls,
        db: Session,
        kind: str,
        libelle: str,
        user: User,
        request: Request,
        manager_cuid: str | None = None,
        direction_id: int | None = None,
        direction_libelle: str | None = None,
    ) -> LabelUsageOut:
        definition = cls.get_definition(kind)
        extra = {}
        if kind in ("directions", "departements") and manager_cuid:
            extra["manager_cuid"] = cls._normalize_manager_cuid(manager_cuid)

        if kind == "departements":
            target_dir_id = direction_id
            if not target_dir_id and direction_libelle:
                d = db.scalar(select(Direction).where(Direction.libelle == direction_libelle))
                if d:
                    target_dir_id = d.id
            if not target_dir_id:
                first_dir = db.scalar(select(Direction).order_by(Direction.id))
                if not first_dir:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Creez d'abord une direction")
                target_dir_id = first_dir.id
            extra["direction_id"] = target_dir_id

            exists = db.scalar(
                select(Departement.id).where(
                    Departement.direction_id == target_dir_id,
                    func.lower(Departement.libelle) == libelle.lower(),
                )
            )
            if exists:
                raise HTTPException(status.HTTP_409_CONFLICT, "Ce departement existe deja pour cette direction")

        item = cls.add_label(db, definition.model, libelle, user, request, "REFERENTIAL_CREATED", **extra)
        mgr_map = cls._resolve_managers_map(db, [item]) if kind in ("directions", "departements") else {}
        dir_name = None
        if kind == "departements":
            d_obj = db.get(Direction, item.direction_id)
            dir_name = d_obj.libelle if d_obj else None

        return LabelUsageOut(
            id=item.id,
            libelle=item.libelle,
            usage=0,
            manager_cuid=getattr(item, "manager_cuid", None),
            managers=mgr_map.get(item.id, []),
            direction_id=getattr(item, "direction_id", None),
            direction_libelle=dir_name,
        )

    @classmethod
    def rename_referential(
        cls,
        db: Session,
        kind: str,
        item_id: int,
        libelle: str,
        user: User,
        request: Request,
        manager_cuid: str | None = None,
        direction_id: int | None = None,
    ) -> LabelUsageOut:
        definition = cls.get_definition(kind)
        item = db.get(definition.model, item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Valeur introuvable")

        if kind == "departements":
            target_dir_id = direction_id or item.direction_id
            exists = db.scalar(
                select(Departement.id).where(
                    Departement.direction_id == target_dir_id,
                    func.lower(Departement.libelle) == libelle.lower(),
                    Departement.id != item.id,
                )
            )
            if exists:
                raise HTTPException(status.HTTP_409_CONFLICT, "Ce departement existe deja pour cette direction")
            item.direction_id = target_dir_id
            item.manager_cuid = cls._normalize_manager_cuid(manager_cuid)
        elif kind == "directions":
            if cls.exists_label(db, definition.model, libelle, exclude_id=item.id):
                raise HTTPException(status.HTTP_409_CONFLICT, "Cette valeur existe deja")
            item.manager_cuid = cls._normalize_manager_cuid(manager_cuid)
        else:
            if cls.exists_label(db, definition.model, libelle, exclude_id=item.id):
                raise HTTPException(status.HTTP_409_CONFLICT, "Cette valeur existe deja")

        old_libelle = item.libelle
        item.libelle = libelle

        usage_map = definition.compute_usage(db)
        usage = usage_map.get(item.id if kind == "flux-types" else item.libelle, 0)
        audit(
            db,
            "REFERENTIAL_UPDATED",
            actor_id=user.id,
            entity=definition.model.__tablename__,
            entity_id=item.id,
            request=request,
            details={"ancien": old_libelle, "nouveau": item.libelle, "manager_cuid": getattr(item, "manager_cuid", None)},
        )
        mgr_map = cls._resolve_managers_map(db, [item]) if kind in ("directions", "departements") else {}
        dir_name = None
        if kind == "departements":
            d_obj = db.get(Direction, item.direction_id)
            dir_name = d_obj.libelle if d_obj else None

        return LabelUsageOut(
            id=item.id,
            libelle=item.libelle,
            usage=usage,
            manager_cuid=getattr(item, "manager_cuid", None),
            managers=mgr_map.get(item.id, []),
            direction_id=getattr(item, "direction_id", None),
            direction_libelle=dir_name,
        )

    @classmethod
    def delete_referential(cls, db: Session, kind: str, item_id: int, user: User, request: Request) -> None:
        definition = cls.get_definition(kind)
        item = db.get(definition.model, item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Valeur introuvable")
        if db.scalar(select(func.count()).select_from(definition.model)) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette liste doit garder au moins une valeur")

        if kind == "flux-types":
            used = db.scalar(select(func.count()).select_from(FluxRequest).where(FluxRequest.flux_type_id == item.id))
            if used:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Utilise par {used} demande(s) : renommez-le plutot que de le supprimer",
                )
        elif kind == "departements":
            used = db.scalar(select(func.count()).select_from(FluxRequest).where(FluxRequest.departement == item.libelle))
            if used:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Utilise par {used} demande(s) : renommez-le plutot que de le supprimer",
                )
        elif kind == "directions":
            # Si des departements ou demandes y sont lies
            depts_count = db.scalar(select(func.count()).select_from(Departement).where(Departement.direction_id == item.id))
            if depts_count:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Cette direction possede {depts_count} departement(s) associe(s) : supprimez d'abord ses departements",
                )

        audit(
            db,
            "REFERENTIAL_DELETED",
            actor_id=user.id,
            entity=definition.model.__tablename__,
            entity_id=item.id,
            request=request,
            details={"libelle": item.libelle},
            commit=False,
        )
        db.delete(item)
        db.commit()

    @classmethod
    def validate_request_labels(cls, db: Session, data: FluxRequestIn) -> str:
        flux_type = db.get(FluxType, data.flux_type_id)
        if not flux_type:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Type de flux inconnu")

        if data.direction:
            dir_obj = db.scalar(select(Direction).where(Direction.libelle == data.direction))
            if not dir_obj:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Direction inconnue")

        dept_exists = db.scalar(select(Departement).where(Departement.libelle == data.departement))
        dir_exists = db.scalar(select(Direction).where(Direction.libelle == data.departement))
        if not dept_exists and not dir_exists:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Departement inconnu")

        zones = set(db.scalars(select(Zone.libelle)))
        countries = set(db.scalars(select(Country.libelle)))
        for i, line in enumerate(data.lines, start=1):
            if line.src_zone not in zones or line.dst_zone not in zones:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Ligne {i} : zone inconnue")
            if line.src_pays not in countries or line.dst_pays not in countries:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Ligne {i} : pays inconnu")

        return flux_type.libelle
