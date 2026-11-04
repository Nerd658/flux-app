"""Sceau cryptographique : empreinte SHA-256 du contenu + signature Ed25519 de chaque validateur.

- Le contenu de la demande est sérialisé de façon canonique (JSON trié) puis haché.
- Chaque décision signe : référence + hash du contenu + niveau + décision + commentaire + date + validateur.
- Toute modification en base (contenu ou décision) rend la vérification invalide.
- Les clés privées sont stockées chiffrées (clé maître KEY_ENCRYPTION_SECRET, hors base).
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FluxRequest, SigningKey, User, Validation

logger = logging.getLogger("seal")

_LINE_FIELDS = ("numero", "src_ip", "src_zone", "src_pays", "src_app", "dst_ip", "dst_ports",
                "protocole", "dst_zone", "dst_pays", "dst_app", "type_acces", "justification")


def _canonical(data: dict) -> bytes:
    # Sérialisation déterministe : mêmes données -> mêmes octets -> même hash
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def utc_iso(dt: datetime) -> str:
    """Date normalisée UTC à la seconde (MySQL DATETIME ne garde ni fuseau ni microsecondes)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat()


# ---------- Contenu de la demande ----------

def content_hash(req: FluxRequest) -> str:
    data = {
        "reference": req.reference,
        "flux_type": req.flux_type_label,
        "demandeur": [
            req.dem_nom,
            req.dem_prenom,
            req.dem_email,
            req.dem_telephone,
            req.dem_statut_pro.value if getattr(req, "dem_statut_pro", None) else "employe",
        ],
        "manager": [req.mgr_nom, req.mgr_prenom, req.mgr_email, req.mgr_telephone],
        "direction": getattr(req, "direction", "") or "",
        "departement": req.departement,
        "periode": req.periode.value,
        "date_debut": req.date_debut.isoformat(),
        "date_fin": req.date_fin.isoformat() if req.date_fin else None,
        "lines": [{f: getattr(l, f) for f in _LINE_FIELDS} for l in sorted(req.lines, key=lambda x: x.numero)],
    }
    return hashlib.sha256(_canonical(data)).hexdigest()


# ---------- Clés des validateurs ----------

def _master_key() -> bytes:
    return get_settings().key_encryption_secret.encode()


def fingerprint(public_pem: str) -> str:
    pub = serialization.load_pem_public_key(public_pem.encode())
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def _register_public_key(db: Session, user: User) -> str:
    """Archive la clé publique courante du validateur (idempotent) et renvoie son empreinte."""
    fp = fingerprint(user.public_key)
    if not db.get(SigningKey, fp):
        db.add(SigningKey(fingerprint=fp, user_id=user.id, public_key=user.public_key))
    return fp


def _generate_keys(db: Session, user: User) -> None:
    """Nouvelle paire Ed25519 : privée chiffrée par la clé maître, publique archivée."""
    priv = Ed25519PrivateKey.generate()
    user.private_key_enc = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(_master_key()),
    ).decode()
    user.public_key = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    _register_public_key(db, user)


def _load_private(user: User) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(user.private_key_enc.encode(), password=_master_key())
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("type de clé inattendu")
    return key


def signing_key_for(db: Session, user: User) -> tuple[Ed25519PrivateKey, bool]:
    """Renvoie la clé privée du validateur, et True si elle a dû être (re)générée.

    Clé absente (première décision) ou indéchiffrable (KEY_ENCRYPTION_SECRET modifié) : une nouvelle
    paire est créée. L'ancienne clé publique reste archivée, donc les signatures passées restent vérifiables.
    """
    if user.public_key and user.private_key_enc:
        try:
            key = _load_private(user)
            _register_public_key(db, user)   # clés créées avant l'historique : archivage au passage
            return key, False
        except (ValueError, TypeError):
            logger.warning("Clé de signature de l'utilisateur %s indéchiffrable : renouvellement", user.id)
            _register_public_key(db, user)   # l'ancienne clé publique reste lisible : on l'archive avant de la remplacer
    _generate_keys(db, user)
    return _load_private(user), True


# ---------- Signature d'une décision ----------

def _decision_payload(req: FluxRequest, v: Validation, validateur_email: str) -> bytes:
    return _canonical({
        "reference": req.reference,
        "content_hash": req.content_hash,
        "niveau": v.niveau,
        "decision": v.decision.value,
        "commentaire": v.commentaire or "",
        "decided_at": utc_iso(v.decided_at),
        "validateur": validateur_email,
    })


def sign_decision(db: Session, req: FluxRequest, v: Validation, validateur: User) -> bool:
    """Signe la décision ; renvoie True si la clé du validateur a été renouvelée."""
    key, renewed = signing_key_for(db, validateur)
    payload = _decision_payload(req, v, validateur.email)
    v.signed_hash = hashlib.sha256(payload).hexdigest()
    v.signature = base64.b64encode(key.sign(payload)).decode()
    v.key_fingerprint = fingerprint(validateur.public_key)
    return renewed


# ---------- Vérification ----------

def verify_request(db: Session, req: FluxRequest) -> dict:
    intact = content_hash(req) == req.content_hash
    sigs = []
    for v in req.validations:
        validateur = db.get(User, v.validateur_id)
        ok = False
        try:
            # Clé publique retrouvée par son empreinte : fonctionne aussi après renouvellement
            archived = db.get(SigningKey, v.key_fingerprint)
            public_pem = archived.public_key if archived and archived.user_id == v.validateur_id else validateur.public_key
            pub = serialization.load_pem_public_key(public_pem.encode())
            if isinstance(pub, Ed25519PublicKey) and fingerprint(public_pem) == v.key_fingerprint:
                pub.verify(base64.b64decode(v.signature), _decision_payload(req, v, validateur.email))
                ok = True
        except (InvalidSignature, ValueError, AttributeError, TypeError):
            ok = False   # fail securely : toute anomalie = signature invalide
        sigs.append({"niveau": v.niveau, "decision": v.decision.value, "signature_valide": ok})
    return {
        "reference": req.reference,
        "contenu_intact": intact,
        "signatures": sigs,
        "document_fiable": intact and all(s["signature_valide"] for s in sigs),
    }
