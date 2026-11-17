# ClubOS

Operating system for clubs and student organizations. FastAPI + PostgreSQL backend, Next.js frontend.

## Run everything (Docker)
```bash
cp .env.example .env        # then set POSTGRES_PASSWORD and SECRET_KEY (instructions inside)
docker compose up --build
# Website  http://localhost        (Caddy is the single public entry point)
# Dev only (docker-compose.override.yml): web :3000, API docs :8000/docs
```
Migrations and default plans/content are applied on start. With `SMTP_HOST` empty, emails (including the
verification link) are printed by `docker compose logs -f worker`.

Make yourself super admin, then enable 2FA in your security settings (required for `/admin`):
```bash
docker compose exec api python -m app.cli make-admin you@example.com
```
**Going live? Read [LAUNCH.md](LAUNCH.md)** (checklist, runbook, honest limits) and run `scripts/verify-deploy.sh https://yourdomain.com`.

## Develop
```bash
# backend (SQLite, auto-creates tables)
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload            # :8000
python -m app.worker                     # second terminal: email

# frontend
cd frontend && cp .env.example .env && npm install && npm run dev     # :3000, proxies /api to :8000
```

## Test
```bash
cd backend && pytest                                                    # SQLite
DATABASE_URL=postgresql://user:pass@localhost/clubos_test pytest        # Postgres (+ concurrency tests)
cd frontend && npx tsc --noEmit && npm run build
```

## What the super admin controls (no deploy needed)
`/admin` → **Page content** (every heading, paragraph, FAQ item, nav link, footer column), **Plans and pricing**
(prices, limits, feature flags, feature lists, "soon" markers), **Offers** (site banner, plan discounts, schedules),
upgrade approvals, review moderation, clubs, users. Limits and flags are enforced by the API immediately.

## Billing (manual, on purpose)
A club owner requests an upgrade (`/upgrade`). You collect payment (bKash, Nagad, bank), then press
"Confirm payment and activate" in `/admin`. Plans expire after the paid months and fall back to Free entitlements
without deleting anything.

## Production checklist (short version; full list in LAUNCH.md)
- `COOKIE_SECURE=true`, real `BASE_URL`/`CORS_ORIGINS`, `NEXT_PUBLIC_SITE_URL`
- Managed Postgres with backups; run `api`, `worker`, `web` as three services from the same repo
- Persistent volume mounted at `MEDIA_DIR` (uploads), or swap `uploads` storage for S3/R2
- Resend (or any SMTP) with a verified sending domain
- Keep Caddy (or another proxy that overwrites X-Forwarded-For) as the only public entry
# ClubOS
