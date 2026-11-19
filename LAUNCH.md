# ClubOS launch guide

## Verdict
Ready for a **closed pilot with 1 to 3 real clubs** once the "Only you can do" list below is complete.
Not ready for an open public launch or a large event spike until a staging load test and the first month of
real-world monitoring are done. Details are in "Known limits".

## What the audit covered and found
| Area | Method | Result |
|---|---|---|
| Authorization | automated sweep of all 105 operations as an anonymous caller | 83/83 protected ones return 401; the 22 public ones are the intended list |
| Dependency vulnerabilities | pip-audit, npm audit | 0 known |
| Static security analysis | bandit | no medium/high findings |
| Backend tests | pytest, 26 tests incl. 3 Postgres-only concurrency races | all pass on SQLite and PostgreSQL 16 |
| Coverage | pytest-cov | ~85% of backend lines. **Frontend has no automated tests.** |
| Real browser | Qt WebEngine (Chromium), 21 screenshots: 3 modes x desktop/mobile, dashboards, admin | 0 console errors after fixes |
| Deploy topology | spoofed-header test direct vs. through Caddy | see "Client IP" below |

Fixed during the audit: spoofable client IP; no verification-email resend; no Terms/Privacy/consent; no password
change, 2FA, data export or account deletion; no unsubscribe; public-by-default profiles and full names on reviews;
session token in login JSON; CSS/URL injection patterns; `javascript:` links from CMS; limit races under concurrency;
no retention jobs, request ids or error tracking; React hydration bug (date formatting) that also reset the chosen
mode; a CSS-layer bug that made phones scroll sideways; grid overflow; per-IP rate limits that would lock out a campus.

## Client IP (read this)
Rate limits and sign-in history need the real visitor IP. Next.js passes `X-Forwarded-For` through untouched, so on its own it is spoofable (reproduced).
Current design:
1. The web app's `/api` route handler works out the visitor IP from the one source it can trust (Vercel's own header on Vercel; Caddy's overwritten
   `X-Forwarded-For` behind Caddy) and forwards it with a shared `PROXY_SECRET`. Visitor-supplied forwarding headers are discarded there.
2. The API trusts the forwarded IP only when the secret matches. Anyone who reaches the API directly (Render's URL is public) is resolved by the
   `TRUSTED_PROXIES` rule instead: the address appended by the host's edge, which a visitor cannot forge.
3. `PROXY_SECRET` (32+ chars) is required in production on both sides; the API refuses to start without it.
Check any deployment with `scripts/verify-deploy.sh https://yourdomain.com` and by opening `/api/whoami` from two different networks.
Never publish the API or web ports directly in the Docker setup (Caddy is the only public entry).

## Only you can do (I cannot)
1. **Domain and HTTPS.** Point DNS at the server, set `DOMAIN=yourdomain.com`; Caddy gets certificates automatically.
2. **Email deliverability, the #1 launch risk.** No email, no registration. Use your Brevo account: verify
   your sending domain, add the SPF, DKIM and DMARC DNS records, fill `SMTP_*`. Then register with a Gmail address **and**
   a college/Bangladeshi provider address and confirm the verification mail arrives in the inbox, not spam.
3. **Secrets.** `POSTGRES_PASSWORD` and `SECRET_KEY` (48+ random chars). Never change `SECRET_KEY` after launch
   (it signs unsubscribe links and encrypts 2FA secrets).
4. **Production flags.** `COOKIE_SECURE=true`, https `BASE_URL` and `CORS_ORIGINS`. The API refuses to start with a weak
   `SECRET_KEY` when `COOKIE_SECURE=true`.
5. **Backups.** Daily Postgres backups plus the media volume. **Do a restore drill once**; an untested backup is a hope.
6. **First admin.** Register, then `docker compose exec api python -m app.cli make-admin you@example.com`, then enable 2FA
   in your security settings (the admin area refuses to open without it). Save the 2FA secret somewhere safe.
7. **Content and prices.** Open `/admin`: review every page's copy, the plan limits and prices, and the contact email.
   Prices I seeded (Pro ৳800, Organization ৳3,500) are guesses; validate with real clubs.
8. **Legal.** Have a Bangladeshi lawyer review `/terms` and `/privacy` (editable in `/admin` under Page content).
   They are plain-language drafts describing what the software actually does. If clubs will register students under
   18, get advice on parental consent.
9. **Monitoring.** Set `SENTRY_DSN`; add an uptime monitor on `https://yourdomain.com/api/health`; check
   `docker compose logs worker` daily at first (failed emails show as `emails failed` on the admin overview).
10. **Load test before a big event** (k6 or similar, against staging, on the real server size). I could not measure
    capacity: the sandbox has 1 CPU shared with the load generator, so my numbers are meaningless as capacity figures.
11. **Pilot first.** One real club, one real event, with you on call. Watch the first 50 registrations.

## Operating runbook
- **Approve a paid plan:** `/admin` > Overview > "Confirm payment and activate" after bKash/Nagad/bank payment arrives.
- **Plan expiry:** automatic; features fall back to Free, nothing is deleted.
- **User lost their 2FA device:** `docker compose exec api python -m app.cli reset-2fa user@example.com`.
- **Deletion request:** the user can self-serve in security settings. Clubs keep anonymous attendance totals.
- **Abuse:** `/admin` > Users > Suspend (sessions end immediately); reviews: Reviews tab.
- **Email stuck:** `/admin` overview shows pending/failed counts; worker retries 5 times with backoff then marks failed.
- **Schema change:** edit `models.py`, `alembic revision --autogenerate -m "..."`, review, commit. Migrations run on start.
- **Regenerate pinned Python deps:** `python -m venv /tmp/v && /tmp/v/bin/pip install -r backend/requirements.in &&
  /tmp/v/bin/pip freeze > backend/requirements.txt` then run the tests.

## Known limits (honest list)
- Rate limiter is in-process memory: run **one** API instance (or move it to Redis first). Free Render allows exactly one anyway.
- Uploads are on local disk: keep the media volume; move to R2/S3 before scaling out.
- No bounce/complaint handling for email (needs Brevo webhooks). Watch your sender reputation; unsubscribe is honoured.
- No automated frontend tests; browser-verified manually in 3 modes on desktop and mobile Chromium only
  (not Safari, Firefox, or real low-end Android devices).
- Not built: certificates, paid events and ticket types, automations, teams/tags, custom pages/domains,
  multi-club organization dashboard, SSO, API keys/webhooks. They appear as "Soon" on the pricing page.
- Search is substring matching (fine to roughly 10k rows).
- Times are entered in the organizer's browser timezone and displayed in Bangladesh time.
- Account deletion cancels the person's upcoming registrations but does not auto-promote waitlisted people.
