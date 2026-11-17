from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./clubos.db"
    base_url: str = "http://localhost:3000"          # frontend origin, used in email links
    cors_origins: str = "http://localhost:3000"      # comma separated
    cookie_secure: bool = False                       # True in production (HTTPS)
    session_ttl_hours: int = 24 * 14
    rate_limit_enabled: bool = True
    secret_key: str = ""                              # REQUIRED in production (>=32 chars): signs unsubscribe links, encrypts 2FA secrets
    trusted_proxies: int = 1                          # proxy hops in front of the API: 1 = web only; 2 = Railway/Cloudflare edge + web
    require_admin_2fa: bool = True
    sentry_dsn: str = ""
    terms_version: str = "2026-11"
    auto_create_tables: bool = True                   # dev convenience; use Alembic in production

    media_dir: str = "./media"                        # mount a persistent volume here in production
    max_upload_mb: int = 5

    smtp_host: str = ""                               # empty = log emails to console instead
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ClubOS <no-reply@clubos.local>"


settings = Settings()
