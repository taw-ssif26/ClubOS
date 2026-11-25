export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public detail?: any) { super(message); }
}

function messageOf(d: any): string {
  if (!d) return "Something went wrong. Try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join("; ");
  if (d.errors) return Object.entries(d.errors).map(([k, v]) => `${k}: ${v}`).join("; ");
  return d.message || "Something went wrong. Try again.";
}

export async function api<T = any>(path: string, init: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init.method || (init.body || init.form ? "POST" : "GET"),
    credentials: "same-origin",
    headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined),
  });
  const text = await res.text();
  let data: any;
  try { data = text ? JSON.parse(text) : undefined; } catch { data = undefined; }
  if (!res.ok) {
    const d = data?.detail;
    throw new ApiError(res.status, messageOf(d), typeof d === "object" ? d?.code : undefined, d);
  }
  return data as T;
}

/** Fetcher for SWR-like usage in effects. */
export const get = <T = any>(path: string) => api<T>(path);
