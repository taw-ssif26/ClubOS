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

    proxy_secret: str = ""                            # shared with the web proxy; lets the API trust the client IP the proxy forwards
    brevo_api_key: str = ""                           # Brevo HTTPS API key (needed where outbound SMTP is blocked, e.g. Render free)
    email_daily_cap: int = 0                          # provider daily limit (Brevo free = 300). 0 = unlimited. Excess waits for tomorrow.
    run_worker_in_api: bool = False                   # run the email worker inside the API process (no separate worker service)
    worker_poll_seconds: int = 900                    # slow poll; emails also send immediately after being queued (lets Neon sleep)
    media_backend: str = "disk"                       # disk | db  (db = images stored in Postgres; for hosts without persistent disks)
    db_pool_size: int = 5
    db_max_overflow: int = 10

    smtp_host: str = ""                               # empty = log emails to console instead
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ClubOS <no-reply@clubos.local>"


settings = Settings()
