"""Dépendances FastAPI : utilisateur courant, contrôle des rôles, protection CSRF."""
import secrets
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User
from app.security import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, decode_access_token, session_fingerprint

_UNAUTHORIZED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Non authentifié")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_protect(request: Request) -> None:
    """Double-submit cookie : l'en-tête doit égaler le cookie pour toute requête modifiante."""
    if request.method in _SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Jeton CSRF invalide")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    if not payload:
        raise _UNAUTHORIZED
    user = db.get(User, int(payload["sub"]))
    # Le rôle est relu en base : un changement de rôle prend effet immédiatement
    if not user or not user.is_active:
        raise _UNAUTHORIZED
    # Mot de passe changé ou réinitialisé depuis l'ouverture de la session : session révoquée
    if not secrets.compare_digest(str(payload.get("pwd", "")), session_fingerprint(user.password_hash)):
        raise _UNAUTHORIZED
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    """Moindre privilège : n'autorise que les rôles listés (refus par défaut)."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé")
        return user
    return checker
