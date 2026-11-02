from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration chargée depuis l'environnement / .env (aucun secret en dur)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=32)          # refuse un secret trop court
    key_encryption_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30                   # session courte par défaut
    cors_origins: list[str] = ["http://localhost:5173"]
    seed_password: str | None = None
    environment: str = "dev"

    # Authentification : « local » (comptes fictifs, en attendant l'AD) ou « ldap » / « ad » (Active Directory)
    auth_mode: Literal["local", "ldap", "ad"] = "local"
    ldap_url: str | None = None                      # ex. ldaps://dc01.domaine.bf:636 (LDAPS obligatoire)
    ldap_upn_suffix: str | None = None               # ex. domaine.bf -> bind « CUID@domaine.bf »
    ldap_base_dn: str | None = None                  # ex. DC=domaine,DC=bf
    ldap_cuid_attribute: str = "sAMAccountName"
    # Active Directory (serveurs multiples, bind DOMAINE\username)
    ad_domain: str | None = None                     # ex. OCITNETAD
    ad_servers_ip: str | None = None                 # ex. 10.0.0.1,10.0.0.2
    ad_response_timeout: int = Field(default=10, validation_alias=AliasChoices("ad_response_timeout", "ad_response_timout"))
    # Compte administrateur local de secours : seul compte à mot de passe local en mode « ldap » / « ad »
    local_admin_cuid: str | None = None
    # Reverse proxies de confiance : seuls eux peuvent transmettre l'IP réelle du poste (X-Forwarded-For)
    trusted_proxies: list[str] = []

    @field_validator("jwt_secret", "key_encryption_secret")
    @classmethod
    def no_placeholder(cls, v: str) -> str:
        # Fail securely : on bloque le démarrage si le secret n'a pas été changé
        if "CHANGE_ME" in v:
            raise ValueError("secret non configuré")
        return v

    @field_validator("cors_origins")
    @classmethod
    def no_wildcard(cls, v: list[str]) -> list[str]:
        # CORS strict : le joker "*" est interdit
        if "*" in v:
            raise ValueError("CORS '*' interdit")
        return v


    @model_validator(mode="after")
    def ldap_complete(self):
        if self.auth_mode == "ldap":
            if not (self.ldap_url and self.ldap_upn_suffix and self.ldap_base_dn):
                raise ValueError("mode ldap : LDAP_URL, LDAP_UPN_SUFFIX et LDAP_BASE_DN sont obligatoires")
            if not self.ldap_url.lower().startswith("ldaps://"):
                raise ValueError("LDAP_URL doit utiliser ldaps:// (mot de passe chiffré sur le réseau)")
        elif self.auth_mode == "ad":
            if not (self.ad_domain and self.ad_servers_ip):
                raise ValueError("mode ad : AD_DOMAIN et AD_SERVERS_IP sont obligatoires")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
