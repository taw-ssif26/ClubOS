## Project: ClubOS
Operating system for clubs and student organizations (Bangladesh first). FastAPI + PostgreSQL | Next.js 16 + React 19 + Tailwind 4 + Motion | Caddy in front.

## Current State (v0.2): audited, hardened, browser-verified. READY FOR A CLOSED PILOT (1-3 clubs) after the checklist in LAUNCH.md. NOT ready for open public launch.
Verified: 29 backend tests pass on PostgreSQL 16 (26 on SQLite), 86% backend coverage, 0 known dependency vulns (pip-audit, npm audit), bandit clean,
83/83 protected endpoints return 401 anonymously, tsc clean, next build passes, 21 screenshots in real Chromium (3 modes x desktop/mobile + dashboards)
with 0 console errors, scripts/verify-deploy.sh passes against the Caddy-fronted stack.
NOT verified: capacity (sandbox had 1 CPU shared with the load generator), Safari/Firefox/real Android, real email deliverability, restore drill.

## Freemium (editable in /admin, enforced by API): Free = 100 members, 3 admin seats, 5 active events, 500 MB, no bulk email/conditional forms/waitlist.
Pro (default ৳800) unlocks scale + email + analytics + themes. Organization/Enterprise headline features are marked "Soon". Manual billing with expiry fallback.

## Key decisions
- Client IP: Next.js passes X-Forwarded-For through UNTOUCHED (reproduced spoofing). Caddy overwrites it (verified). Never publish api/web ports. TRUSTED_PROXIES counts appending proxies in front of web.
- Authenticated rate limits key on SESSION not IP (campus Wi-Fi = one IP for a whole college). Anonymous limits per IP are generous.
- Session token only in HttpOnly cookie. Origin check on cookie-authenticated writes. 2FA (TOTP, encrypted at rest, replay-protected) REQUIRED for platform admins.
- Privacy: profiles private by default; reviews show "First L."; consent recorded at signup; self-serve data export and account deletion; unsubscribe on all club email.
- CSS: component styles live in @layer components so Tailwind utilities win (an unlayered .btn broke `hidden` and caused mobile overflow).
- Dates are formatted by hand in Dhaka time (Intl differs between Node and Chrome -> hydration errors).
- Tooling note: screenshot rig = Qt WebEngine under xvfb (scroll-and-stitch capture; resizing the window distorts vh units).

## Free hosting (v0.3): Vercel + Render + Neon + Brevo. See DEPLOY-FREE.md. Verified locally, NOT on the real services.
Adapted for free-tier facts (checked Nov 2026): Render free blocks SMTP / no disk / no workers / sleeps 15 min; Neon free sleeps after 5 min, 100 CU-h, 1 GB;
Brevo free 300 emails/day; Vercel Hobby is NON-COMMERCIAL (must move to Pro before charging clubs).
Built: Brevo HTTPS sender, EMAIL_DAILY_CAP + transactional-first priority, in-API worker (wakes on commit, 15-min poll so Neon can sleep),
/ping (no DB), images in Postgres (MEDIA_BACKEND=db), retrying authenticated /api proxy (PROXY_SECRET, cold-start retry, no POST replay),
render.yaml, vercel.json, encrypted nightly backup workflow (round-trip tested).
Tests: 36 pass on PostgreSQL, 33 + 3 skipped on SQLite and in the pinned clean venv.

## Key Files: LAUNCH.md (go-live checklist/runbook/limits) | scripts/verify-deploy.sh | Caddyfile | backend/app/{net,ratelimit,deps}.py (trust + auth)
backend/app/routers/account.py (2FA, export, delete, unsubscribe) | backend/app/seed.py (all default copy + legal drafts) | frontend/src/app/globals.css

## Known gaps: see LAUNCH.md "Known limits". Biggest: email deliverability untested, no frontend tests, single-instance rate limiter, no bounce handling, local-disk uploads, legal text needs lawyer review.

## Next Step: do the "Only you can do" list in LAUNCH.md (domain, Brevo verified sender + SPF/DKIM/DMARC, secrets, backups + restore drill, first admin + 2FA, lawyer review), run scripts/verify-deploy.sh, then pilot one club and one event.
