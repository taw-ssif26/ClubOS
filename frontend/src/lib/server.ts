import { apiBase } from "./apiurl";

const API = apiBase();

/** Server-side fetch against the API. Returns null on any failure so pages degrade instead of crashing. */
export async function sget<T = any>(path: string, revalidate = 15): Promise<T | null> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(`${API}${path}`, { next: { revalidate }, signal: AbortSignal.timeout(25_000) });
      if (res.ok) return (await res.json()) as T;
      if (res.status < 500 || ![502, 503, 504].includes(res.status)) return null;  // real answer (404 etc.): no point retrying
    } catch { /* API still waking up */ }
    await new Promise((r) => setTimeout(r, 4000));
  }
  return null;
}

export const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
