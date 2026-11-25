// Deterministic date formatting in Bangladesh time (UTC+6, no DST). Intl output differs between Node and Chrome
// ICU builds (spacing, am/pm case), which causes React hydration mismatches, so we format by hand.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type Opts = { weekday?: string; day?: "numeric" | "2-digit"; month?: string; year?: string; hour?: string; minute?: string; hour12?: boolean };

export function fmtDate(iso?: string | null, o: Opts = { day: "numeric", month: "short", year: "numeric" }): string {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() + 6 * 3600 * 1000);
  const day = d.getUTCDate();
  const date = [o.weekday ? `${DAYS[d.getUTCDay()]},` : "", o.day ? (o.day === "2-digit" ? String(day).padStart(2, "0") : String(day)) : "", o.month ? MONTHS[d.getUTCMonth()] : "", o.year ? String(d.getUTCFullYear()) : ""]
    .filter(Boolean).join(" ");
  let time = "";
  if (o.hour) {
    const h = d.getUTCHours();
    time = `${h % 12 === 0 ? 12 : h % 12}:${String(d.getUTCMinutes()).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
  }
  return date && time ? `${date}, ${time}` : date || time;
}
export const fmtDateTime = (iso?: string | null) => fmtDate(iso, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true });
export const fmtTime = (iso?: string | null) => fmtDate(iso, { hour: "numeric", minute: "2-digit", hour12: true });
export const day = (iso: string) => fmtDate(iso, { day: "2-digit" });
export const mon = (iso: string) => fmtDate(iso, { month: "short" });
export const bytes = (n: number) => (n < 1024 ** 2 ? `${Math.round(n / 1024)} KB` : n < 1024 ** 3 ? `${(n / 1024 ** 2).toFixed(1)} MB` : `${(n / 1024 ** 3).toFixed(1)} GB`);
export const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
export const toLocalInput = (iso?: string | null) => (iso ? new Date(new Date(iso).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "");
export const fromLocalInput = (v: string) => (v ? new Date(v).toISOString() : null);
