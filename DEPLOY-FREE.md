# Free deployment: Vercel + Render + Neon (+ Brevo)

```
Browser -> Vercel (Next.js site + /api proxy) -> Render (FastAPI + email worker) -> Neon (Postgres)
                                                       \-> Brevo (HTTPS email API)
```
Limits below were checked against each provider's docs in November 2026. **They change; re-check before you rely on them.**
I tested every behavior locally (proxy, IP trust, cold-start retry, in-API worker, images in Postgres, backups). I could **not** test on
the real Vercel/Render/Neon/Brevo services from my sandbox, so expect to fix small things on the first deploy.

## Read first: what free costs you
| Limit | Effect on ClubOS | What we did |
|---|---|---|
| Render free sleeps after 15 idle minutes; waking takes about a minute | first visitor after a quiet spell waits | proxy and SSR retry for up to ~30s; UptimeRobot ping keeps it awake |
| Render free: 750 instance-hours/month per workspace | one always-on service fits (about 744 h) | run only the API on Render |
| Render free blocks outbound SMTP and has no disk or background workers | email, uploads, worker all break as-built | Brevo HTTPS API, images in Postgres, worker runs inside the API |
| Neon free: scales to zero after 5 min, 100 compute-hours/month, 1 GB storage | an always-awake DB would exhaust the hours | `/ping` never touches the DB, slow worker poll, small pool |
| Brevo free: 300 emails/day (from my research; check your plan) | a 1,000-member campaign takes about 4 days | queue drains daily at `EMAIL_DAILY_CAP=300`; verification emails jump the queue |
| Vercel Hobby is for **non-commercial** use only | **you may not charge clubs while on Hobby** | fine for a free pilot; move to Pro (~$20/month) before taking payments |
| Uploads in Postgres | each image uses your 1 GB Neon storage | uploads capped at 1 MB; fine for logos and banners, move to R2/S3 later |

## A domain is strongly recommended (about ৳1,000/year)
Brevo requires the From address (`SMTP_FROM`) to be a **verified sender** in your Brevo account (Settings > Senders). You can verify a single address
without a domain, but mail "from" a Gmail/Outlook address commonly lands in spam because it can't pass authentication for that provider's domain
(general email knowledge, not something I tested). For real students, verify your own domain in Brevo (SPF, DKIM) and add a DMARC record.

## Steps
**0. GitHub.** Create a **private** repository and push the `clubos` folder (the repo root contains `backend/`, `frontend/`, `render.yaml`).
Generate three secrets and keep them in a password manager:
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"` (run three times: `SECRET_KEY`, `PROXY_SECRET`, `BACKUP_PASSPHRASE`).
Never change `SECRET_KEY` after launch.

**1. Neon (database).** neon.com > new project, region **AWS Asia Pacific (Singapore)**. In *Connect*, turn **off** "Pooled connection" and copy the
connection string (host has no `-pooler`; it ends with `?sslmode=require`). This is `DATABASE_URL`.

**2. Render (API).** Dashboard > New > **Blueprint** > select the repo (it reads `render.yaml`). Fill the prompted values:
`DATABASE_URL` (Neon), `SECRET_KEY`, `PROXY_SECRET`, `BREVO_API_KEY` (step 4), `SMTP_FROM` (`ClubOS <no-reply@yourdomain.com>`, a verified Brevo sender),
and `BASE_URL` + `CORS_ORIGINS` (use `https://yourdomain.com`; if you have no domain yet use your `https://<name>.vercel.app` and update later).
Deploy. When it is live, open `https://<your-api>.onrender.com/ping`: expect `{"ok":true}`. The first start also runs the database migrations.

**3. Vercel (website).** vercel.com > Add New > Project > import the repo. **Root Directory: `frontend`**. Environment variables:
| Name | Value |
|---|---|
| `API_URL` | `https://<your-api>.onrender.com` |
| `PROXY_SECRET` | the same value you gave Render |
| `NEXT_PUBLIC_SITE_URL` | `https://yourdomain.com` |

Deploy, then Settings > Domains > add your domain and create the DNS records Vercel shows. Make sure Render's `BASE_URL` and
`CORS_ORIGINS` equal the final site address exactly, then redeploy the API.

**4. Brevo (email).** You already have the account. In Brevo: Settings > **Senders, Domains & Dedicated IPs** > make sure your sender address (or domain) is
verified and authenticated (SPF/DKIM). Then **SMTP & API > API keys**: create a key (starts with `xkeysib-`) and put it in Render as `BREVO_API_KEY`.
Use the **API key**, not the SMTP key (Render's free plan blocks SMTP). `SMTP_FROM` must use the verified sender address. Register with a Gmail address
**and** a college address and confirm the verification email arrives in the inbox, not spam.

**5. Keep the API awake.** uptimerobot.com (free) > HTTP monitor on `https://<your-api>.onrender.com/ping`, every 5 minutes. (I did not verify
UptimeRobot's current free terms.) Always monitor `/ping`, never `/health`: `/health` queries the database and would keep Neon awake all month.

**6. First admin.** Render free has no shell, so run the command from your own computer against Neon:
```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
DATABASE_URL='<neon direct url>' python -m app.cli make-admin you@example.com
```
Register on the site first, then run it, then enable 2FA in `/me?tab=security` (the admin area requires it). Same method for `reset-2fa`.

**7. Verify.** `./scripts/verify-deploy.sh https://yourdomain.com` (needs a Unix shell; Git Bash or WSL works on Windows). Then check your IP is resolved
correctly: open `https://yourdomain.com/api/whoami` on your phone using mobile data and again on Wi-Fi. You must see **two different addresses**
and neither may be a Vercel or Render address.

**8. Backups.** GitHub repo > Settings > Secrets > Actions: add `DATABASE_URL` (Neon direct) and `BACKUP_PASSPHRASE`. Run the **backup** workflow once by hand
(Actions tab > backup > Run workflow). Download the artifact and **do one restore test** (`gpg -d file | gunzip | psql <scratch db>`).
Neon's own point-in-time restore window on the free plan is short; I did not verify it, so treat these nightly dumps as your real backup.

## Operating notes
- **Cold start**: after a long idle the first request can take about a minute. The site retries and shows a "starting up" message instead of crashing.
- **Neon budget**: 100 compute-hours/month. Each visit wakes the database for at least 5 minutes. Watch *Monitoring* in Neon during the first weeks.
- **Email cap**: `EMAIL_DAILY_CAP` is set to 300 (Brevo free); change it if your plan differs. Bulk campaigns are queued behind verification and confirmation emails.
- **Images**: if Neon storage nears 1 GB, tell clubs to use smaller images, or move to Cloudflare R2/S3 (needs a code change in `ops.py` and `main.py`).
- **Deploys**: pushing to GitHub redeploys both services. Migrations run on every API start.
- **When you start charging clubs**: move the site off Vercel Hobby (Vercel Pro, or host the Next.js app on Render's paid plan), and consider a paid Render
  instance to remove the sleep. Do this before the first payment, not after.

## Troubleshooting
**First, open `https://yoursite/status`.** It tests the Vercel-to-Render link and prints plain-English hints (no secrets shown).
- **Home says "We'll be right back" and registering says "Not Found"**: the site can't reach the API. Almost always `API_URL` in Vercel: it must be exactly
  `https://<name>.onrender.com` (no trailing slash, no spaces, not the Vercel address). Newer code tolerates a trailing slash, but the value must still point at Render.
  **After changing any Vercel environment variable you must redeploy** (Deployments > ... > Redeploy); running deployments keep the old values.
- **`/status` says the API answered 404**: Render isn't serving the API (a failed deploy makes Render answer 404). Open `https://<name>.onrender.com/ping` yourself; it must show `{"ok":true}`. If not, read the Render logs.
- **`/status` says it can't reach the API**: wrong spelling in `API_URL`, or the Render service is suspended.
- **Site shows "We'll be right back"**: the API is waking or down. Open `/ping` on the Render URL; check Render logs.
- **Login works but you get logged out / 403 on actions**: `BASE_URL` / `CORS_ORIGINS` on Render don't exactly match the site address (including `https://`, no trailing slash).
- **API crashes at boot**: Render logs. Usually `SECRET_KEY`/`PROXY_SECRET` shorter than 32 characters, or a wrong `DATABASE_URL`.
- **No verification email**: Render logs for `brevo 4xx`. A `400 ... sender ... invalid` means `SMTP_FROM` is not a verified sender in Brevo; `401` means a wrong key (use the API key, not the SMTP key).
- **Everyone shares one IP in `/api/whoami`**: `PROXY_SECRET` differs between Vercel and Render.
