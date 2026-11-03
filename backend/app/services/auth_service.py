import os
import secrets

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit, client_agent, client_ip
from app.config import get_settings
from app.directory import DirectoryUnavailable, DirectoryUser, ad_authenticate
from app.models import Role, User
from app.rate_limit import login_limiter
from app.schemas import ProfileUpdateIn
from app.security import (
    clear_session_cookies,
    create_access_token,
    hash_password,
    session_fingerprint,
    set_session_cookies,
    verify_password,
)

NO_LOCAL_PASSWORD = "!annuaire"
_INVALID_CREDENTIALS = HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")


class AuthService:
    @staticmethod
    def sync_from_directory(db: Session, ident: DirectoryUser) -> User:
        """Cree un utilisateur demandeur au premier passage, ou rafraichit son identite."""
        user = db.scalar(select(User).where(User.cuid == ident.cuid))
        email = (ident.email or f"{ident.cuid.lower()}@annuaire.invalid").lower()
        taken = db.scalar(select(User.id).where(func.lower(User.email) == email, User.cuid != ident.cuid))
        if taken:
            email = f"{ident.cuid.lower()}@annuaire.invalid"

        values = dict(
            nom=ident.nom,
            prenom=ident.prenom,
            email=email,
            telephone=ident.telephone[:30],
            departement=ident.departement[:150],
        )
        if user is None:
            user = User(
                cuid=ident.cuid,
                nom=ident.nom,
                prenom=ident.prenom,
                email=email,
                telephone=ident.telephone[:30],
                departement=ident.departement[:150],
                role=Role.demandeur,
                password_hash=NO_LOCAL_PASSWORD,
            )
            db.add(user)
        else:
            if ident.nom and ident.nom != ident.cuid:
                user.nom = ident.nom
            elif not user.nom:
                user.nom = ident.nom

            if ident.prenom and ident.prenom != "-":
                user.prenom = ident.prenom

            if ident.email and not ident.email.endswith("@annuaire.invalid"):
                user.email = email

            if ident.telephone:
                user.telephone = ident.telephone[:30]

            if ident.departement and ident.departement != "Non renseignee":
                user.departement = ident.departement[:150]
        db.flush()
        return user

    @classmethod
    def update_profile(
        cls, db: Session, user: User, data: ProfileUpdateIn, request: Request
    ) -> User:
        email = str(data.email).lower().strip()
        taken = db.scalar(select(User.id).where(func.lower(User.email) == email, User.id != user.id))
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette adresse email est deja utilisee")

        old_profile = {
            "nom": user.nom,
            "prenom": user.prenom,
            "email": user.email,
            "statut_pro": user.statut_pro.value if user.statut_pro else None,
        }
        user.nom = data.nom.strip()
        user.prenom = data.prenom.strip()
        user.email = email
        if data.telephone is not None:
            user.telephone = data.telephone.strip()
        if data.departement:
            user.departement = data.departement.strip()
        if data.statut_pro:
            user.statut_pro = data.statut_pro

        db.flush()
        audit(
            db,
            "USER_PROFILE_UPDATED",
            actor_id=user.id,
            entity="user",
            entity_id=user.id,
            request=request,
            details={
                "ancien": old_profile,
                "nouveau": {
                    "nom": user.nom,
                    "prenom": user.prenom,
                    "email": user.email,
                    "statut_pro": user.statut_pro.value if user.statut_pro else None,
                },
            },
        )
        return user

    @classmethod
    def login(
        cls,
        db: Session,
        cuid_raw: str,
        password: str,
        request: Request,
        response: Response,
        ad_auth_fn=None,
    ) -> User:
        settings = get_settings()
        cuid = cuid_raw.upper()
        trace = {"cuid": cuid, "poste": client_agent(request)}
        rate_key = f"{client_ip(request)}|{cuid}"

        if login_limiter.is_blocked(rate_key):
            audit(db, "LOGIN_BLOCKED", request=request, details=trace)
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives, reessayez plus tard")

        rescue = bool(settings.local_admin_cuid and cuid == settings.local_admin_cuid.upper())
        has_ad_config = bool(
            (os.getenv("AD_SERVERS_IP") or settings.ad_servers_ip)
            and (os.getenv("AD_DOMAIN") or settings.ad_domain)
        )
        is_directory_mode = settings.auth_mode in ("ldap", "ad") or (
            has_ad_config and "PYTEST_CURRENT_TEST" not in os.environ
        )
        authenticate_dir = ad_auth_fn or ad_authenticate

        if is_directory_mode and not rescue:
            try:
                ident = authenticate_dir(cuid, password)
            except DirectoryUnavailable:
                audit(db, "LOGIN_FAILED", request=request, details={**trace, "motif": "annuaire indisponible"})
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "Annuaire indisponible, reessayez plus tard"
                )
            if ident:
                user = cls.sync_from_directory(db, ident)
                mode = "annuaire"
            else:
                # Si le compte n'existe pas dans l'annuaire d'entreprise (ex: comptes de validation/test MGR00001, SECU0001, RSSI0001, ADMN0001),
                # on permet la connexion locale aux comptes validateurs/admin possedant un mot de passe applicatif valide
                local_user = db.scalar(select(User).where(User.cuid == cuid))
                if (
                    local_user
                    and local_user.role in (Role.manager, Role.securite, Role.rssi, Role.admin)
                    and local_user.password_hash
                    and local_user.password_hash != NO_LOCAL_PASSWORD
                ):
                    ok = verify_password(password, local_user.password_hash)
                    if (
                        not ok
                        and settings.seed_password
                        and secrets.compare_digest(password.encode(), settings.seed_password.encode())
                    ):
                        ok = True
                        local_user.password_hash = hash_password(password)
                        db.commit()

                    if ok:
                        user = local_user
                        mode = "local"
                    else:
                        user = None
                else:
                    user = None
        else:
            user = db.scalar(select(User).where(User.cuid == cuid))
            ok = verify_password(password, user.password_hash if user else None)
            mode = "secours" if is_directory_mode else "local"

            if is_directory_mode:
                if not ok or user.role != Role.admin:
                    user = None
            elif not ok:
                if (
                    settings.environment == "dev"
                    and settings.seed_password
                    and secrets.compare_digest(password.encode(), settings.seed_password.encode())
                ):
                    existing = db.scalar(select(User).where(User.cuid == cuid))
                    if existing is not None:
                        existing.password_hash = hash_password(password)
                        db.commit()
                        user = existing
                        mode = "local"
                    else:
                        user = cls.sync_from_directory(
                            db, DirectoryUser(cuid, cuid, "-", None, "", "Non renseignee")
                        )
                        mode = "annuaire fictif"
                else:
                    user = None

        if not user or not user.is_active:
            db.rollback()
            login_limiter.register_failure(rate_key)
            audit(db, "LOGIN_FAILED", request=request, details=trace)
            raise _INVALID_CREDENTIALS

        login_limiter.reset(rate_key)
        token = create_access_token(user.id, user.role.value, session_fingerprint(user.password_hash))
        set_session_cookies(response, token)
        audit(db, "LOGIN_SUCCESS", actor_id=user.id, request=request, details={**trace, "mode": mode})
        return user

    @staticmethod
    def logout(db: Session, user: User, request: Request, response: Response) -> None:
        clear_session_cookies(response)
        audit(
            db,
            "LOGOUT",
            actor_id=user.id,
            request=request,
            details={"cuid": user.cuid, "poste": client_agent(request)},
        )
