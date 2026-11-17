const API = process.env.API_URL || "http://localhost:8000";

/** Server-side fetch against the API. Returns null on any failure so pages degrade instead of crashing. */
export async function sget<T = any>(path: string, revalidate = 15): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
