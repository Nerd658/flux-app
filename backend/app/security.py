"""Hachage des mots de passe, jetons JWT et cookies de session."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Response

from app.config import get_settings

settings = get_settings()
_ph = PasswordHasher()  # Argon2id, paramètres par défaut recommandés

ACCESS_COOKIE = "access_token"   # HttpOnly : inaccessible au JavaScript (anti-XSS)
CSRF_COOKIE = "csrf_token"       # lisible par le JS pour le double-submit
CSRF_HEADER = "X-CSRF-Token"

# Hash factice : vérifié quand l'email n'existe pas, pour un temps de réponse constant
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def session_fingerprint(password_hash: str) -> str:
    """Empreinte courte du hash du mot de passe, portée par le jeton de session.
    Elle change à chaque nouveau mot de passe : toutes les sessions ouvertes deviennent invalides
    (réinitialisation par l'administrateur, changement par l'utilisateur), sans table de révocation."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_access_token(user_id: int, role: str, fingerprint: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "pwd": fingerprint,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        # Algorithme imposé : empêche l'attaque "alg=none" / confusion d'algorithme
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                          options={"require": ["sub", "exp", "iat", "pwd"]})
    except jwt.PyJWTError:
        return None


def set_session_cookies(response: Response, token: str) -> None:
    secure = (
        settings.cookie_secure
        if settings.cookie_secure is not None
        else (settings.environment != "dev")
    )
    same_site = "strict" if secure else "lax"
    max_age = settings.access_token_minutes * 60
    response.set_cookie(ACCESS_COOKIE, token, max_age=max_age, httponly=True,
                        secure=secure, samesite=same_site, path="/")
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(32), max_age=max_age,
                        httponly=False, secure=secure, samesite=same_site, path="/")


def clear_session_cookies(response: Response) -> None:
    secure = (
        settings.cookie_secure
        if settings.cookie_secure is not None
        else (settings.environment != "dev")
    )
    same_site = "strict" if secure else "lax"
    for path in ("/", "/api"):
        response.delete_cookie(ACCESS_COOKIE, path=path, httponly=True, secure=secure, samesite=same_site)
        response.delete_cookie(ACCESS_COOKIE, path=path, httponly=False, secure=secure, samesite=same_site)
        response.delete_cookie(ACCESS_COOKIE, path=path)
        response.delete_cookie(CSRF_COOKIE, path=path, httponly=False, secure=secure, samesite=same_site)
        response.delete_cookie(CSRF_COOKIE, path=path)
