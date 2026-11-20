import { apiBase } from "@/lib/apiurl";

/** Deployment self-check: open https://yoursite/status. Reveals no secrets (host name and yes/no flags only). */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET() {
  const raw = process.env.API_URL;
  const base = apiBase();
  const t0 = Date.now();
  let status = 0, error = "";
  try {
    const r = await fetch(`${base}/ping`, { cache: "no-store", signal: AbortSignal.timeout(55_000) });
    status = r.status;
  } catch (e: any) {
    error = String(e?.cause?.code || e?.message || e);
  }
  const hints: string[] = [];
  if (!raw) hints.push("API_URL is NOT set on this deployment (using http://localhost:8000). Set it in Vercel > Settings > Environment Variables, then redeploy.");
  if (raw && (raw !== raw.trim() || raw.trim().endsWith("/"))) hints.push("API_URL had a trailing slash or spaces. This version fixes that automatically, but clean the value anyway.");
  if (status === 404) hints.push("The API answered 404 for /ping: API_URL points at the wrong service, or the Render API is not running (a failed deploy makes Render answer 404). Open the Render URL + /ping yourself.");
  if (status >= 500) hints.push("The API is up but erroring or still waking from sleep. Wait a minute and refresh; check the Render logs.");
  if (error) hints.push(`Cannot reach the API (${error}). Check API_URL spelling, and that the Render service is deployed and not suspended.`);
  if (!process.env.PROXY_SECRET) hints.push("PROXY_SECRET is not set here: the API will see every visitor as the same IP. Set the same value as on Render.");
  return Response.json({
    ok: status === 200,
    api_host: new URL(base).host,
    api_status: status || null,
    api_error: error || null,
    api_ms: Date.now() - t0,
    proxy_secret_set: Boolean(process.env.PROXY_SECRET),
    site_url_set: Boolean(process.env.NEXT_PUBLIC_SITE_URL),
    on_vercel: process.env.VERCEL === "1",
    hints,
  }, { headers: { "Cache-Control": "no-store" } });
}
