/** API_URL as typed into a dashboard is often messy: trailing slash ("https://x.onrender.com/"), stray spaces, or no scheme.
 *  A trailing slash produces "//path" which FastAPI answers with 404 for every request. Normalize once, here. */
export function apiBase(): string {
  let u = (process.env.API_URL || "http://localhost:8000").trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  return u;
}
