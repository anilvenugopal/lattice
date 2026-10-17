"""Settings read from environment variables or `.env`. See `.env.example`."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Lattice"
    app_env: str = "development"
    # Logo shown in the top bar and on sign-in pages: one file for light mode, one for dark.
    brand_logo_light: str = "/static/brand/logo-light.svg"
    brand_logo_dark: str = "/static/brand/logo-dark.svg"
    # Show APP_NAME next to the logo. Set false when the logo files already contain the name.
    brand_show_name: bool = True
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./data/lattice.kernel.db"

    session_idle_minutes: int = 480
    # None = secure cookies in production or over HTTPS (see lattice/kernel/auth/cookies.py).
    cookie_secure: bool | None = None
    session_max_hours: int = 24
    bcrypt_rounds: int = 12

    password_login_enabled: bool = True

    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/auth/oidc/callback"
    oidc_scopes: str = "openid email profile"
    oidc_provider_label: str = "Single sign-on"
    oidc_default_role: str = ""
    # Link an SSO identity to an existing account by email even when the token does not
    # assert email_verified. Only for an identity provider whose emails your organisation controls.
    oidc_trust_email: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id)


settings = Settings()
