import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import migrate_schema
from app.routers import admin, auth, public, referentiels, requests
from app.security import CSRF_HEADER

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app import seed
        seed.run()
    except Exception as exc:
        logger.error("Erreur lors de l'initialisation automatique de la base de donnees : %s", exc)
        migrate_schema()
    yield


is_dev = settings.environment == "dev"
app = FastAPI(
    title="Demandes d'ouverture de flux",
    # Documentation interactive désactivée hors dev (réduction de surface d'attaque)
    docs_url="/api/docs" if is_dev else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if is_dev else None,
    lifespan=lifespan,
)

# CORS strict : origines explicites, cookies autorisés, méthodes/en-têtes limités
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", CSRF_HEADER],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if request.url.path.startswith("/api/docs"):
        # Swagger UI charge ses scripts depuis un CDN : CSP assouplie uniquement en dev
        return response
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store"   # pas de données sensibles en cache
    if not is_dev:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Minimisation : on renvoie le champ fautif et le message, jamais la valeur saisie (ex. mot de passe)
    errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Fail securely : détail complet en log serveur, seul un numéro d'incident est renvoyé au client
    incident = secrets.token_hex(3).upper()
    logger.exception("Incident %s : erreur non gérée sur %s %s", incident, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Erreur interne (incident {incident})"})


app.include_router(auth.router)
app.include_router(referentiels.router)
app.include_router(requests.router)
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
