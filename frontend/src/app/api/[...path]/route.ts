import type { NextRequest } from "next/server";

/**
 * Same-origin proxy to the API (keeps the session cookie first-party) with three jobs a plain rewrite can't do:
 *  1. Forward the REAL client IP, authenticated with PROXY_SECRET, so the API can trust it even when the API's own
 *     URL is publicly reachable (Render). Spoofed forwarding headers from visitors are discarded here.
 *  2. Survive cold starts: a sleeping free-tier API answers 502/503/504 for up to a minute; we retry instead of failing.
 *  3. Pass Set-Cookie headers through intact.
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const DROP_REQ = new Set(["host", "connection", "content-length", "accept-encoding", "transfer-encoding", "keep-alive", "upgrade",
  "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-port", "x-real-ip", "x-vercel-forwarded-for",
  "x-vercel-ip-country", "x-proxy-secret", "x-client-ip"]);
const DROP_RES = new Set(["content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive", "set-cookie"]);

/** Which header to believe depends on who sits in front of us: only Vercel's edge is trusted to set its own. */
function clientIp(req: NextRequest): string {
  const h = req.headers;
  if (process.env.VERCEL === "1") {
    const v = h.get("x-vercel-forwarded-for") || h.get("x-real-ip");
    if (v) return v.split(",")[0].trim();
  }
  const xff = h.get("x-forwarded-for");
  return xff ? xff.split(",").pop()!.trim() : "";  // behind Caddy: the LAST entry is the address Caddy itself saw
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const api = process.env.API_URL || "http://localhost:8000";
  const url = `${api}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((v, k) => { if (!DROP_REQ.has(k.toLowerCase())) headers.set(k, v); });
  const ip = clientIp(req);
  if (ip) headers.set("x-client-ip", ip);
  if (process.env.PROXY_SECRET) headers.set("x-proxy-secret", process.env.PROXY_SECRET);

  const idempotent = req.method === "GET" || req.method === "HEAD";
  const body = idempotent ? undefined : await req.arrayBuffer();

  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const res = await fetch(url, { method: req.method, headers, body, redirect: "manual", cache: "no-store", signal: AbortSignal.timeout(50_000) });
      // 502/503/504 come from the host's gateway while the API wakes up (our API never emits them), so the request wasn't processed.
      if (![502, 503, 504].includes(res.status)) {
        const out = new Headers();
        res.headers.forEach((v, k) => { if (!DROP_RES.has(k.toLowerCase())) out.append(k, v); });
        for (const c of res.headers.getSetCookie()) out.append("set-cookie", c);
        return new Response(res.status === 204 || res.status === 304 ? null : res.body, { status: res.status, headers: out });
      }
    } catch {
      if (!idempotent) break;  // a dropped connection mid-POST might have been processed: never replay it
    }
    await sleep(3000 * (attempt + 1));
  }
  return Response.json({ detail: "The service is starting up. Please try again in a few seconds." }, { status: 503, headers: { "Retry-After": "10" } });
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
