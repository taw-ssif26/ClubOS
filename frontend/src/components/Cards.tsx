import Link from "next/link";
import { day, fmtTime, mon } from "@/lib/format";
import { locationLine } from "@/lib/places";
import { Pic } from "./Pic";
import { Seal, Stars } from "./ui";

const km = (d?: number | null) => (d == null ? "" : d < 1 ? "under 1 km away" : `${d} km away`);

export function ClubCard({ c }: { c: any }) {
  const where = locationLine(c.location);
  return (
    <Link href={`/c/${c.slug}`} className="panel sheen block p-6 group transition-transform duration-500 hover:-translate-y-1">
      <div className="flex items-start gap-4">
        <Pic src={c.logo_url} className="w-14 h-14 object-cover border border-line" style={{ borderRadius: "var(--r)" }}
          fallback={<span className="display w-14 h-14 grid place-items-center text-3xl border border-[var(--line-strong)]" style={{ borderRadius: "var(--r)", color: "var(--accent)" }}>{c.name[0]}</span>} />
        <div className="min-w-0">
          <h3 className="display h-md truncate">{c.name} {c.verified && <Seal />}</h3>
          <p className="muted text-sm capitalize">{c.category}{c.institution ? ` · ${c.institution.name}` : ""}</p>
        </div>
      </div>
      <p className="muted mt-4 text-[.93rem] line-clamp-2 min-h-[3em]">{c.description || "No description yet."}</p>
      {(where || c.distance_km != null) && <p className="text-sm mt-3" style={{ color: "var(--accent)" }}>{[where, km(c.distance_km)].filter(Boolean).join(" · ")}</p>}
      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="flex items-center gap-2"><Stars value={c.rating?.average} size={14} /><span className="muted">{c.rating?.count ? `${c.rating.average} (${c.rating.count})` : "New"}</span></span>
        <span className="muted group-hover:text-[var(--accent)] transition-colors">{c.join_policy === "open" ? "Open to join" : c.join_policy === "invite" ? "Invite only" : "Request to join"}</span>
      </div>
    </Link>
  );
}

/** Every event is a ticket: date block on the body, venue and seats on the stub. */
export function TicketCard({ e }: { e: any }) {
  const seats = e.capacity ? `${e.registered} / ${e.capacity} seats` : `${e.registered} going`;
  const full = e.capacity && e.registered >= e.capacity;
  const where = e.location?.mode === "online" ? "Online" : [e.location?.mode === "hybrid" ? "Hybrid" : "", e.venue || e.location?.place_name].filter(Boolean).join(" · ");
  return (
    <Link href={`/e/${e.slug}`} className="ticket block group" style={{ ["--cut" as any]: "70%", opacity: e.phase === "past" ? .8 : 1 }}>
      <div className="p-6 pb-7 flex gap-5" style={{ minHeight: 168 }}>
        <div className="text-center shrink-0 w-14">
          <p className="display" style={{ fontSize: "2.6rem", lineHeight: 1, color: "var(--accent)" }}>{day(e.starts_at)}</p>
          <p className="muted text-sm">{mon(e.starts_at)}</p>
        </div>
        <div className="min-w-0">
          {e.phase === "ongoing" && <span className="tag mb-2" style={{ color: "var(--ok)", borderColor: "var(--ok)" }}>● Happening now</span>}
          {e.phase === "past" && <span className="tag mb-2">Ended</span>}
          <h3 className="display h-md line-clamp-2">{e.title}</h3>
          <p className="muted text-sm mt-1">{e.club?.name}</p>
        </div>
      </div>
      <div className="perf" />
      <div className="stub px-6 pb-5 flex items-center justify-between text-sm gap-3">
        <span className="muted truncate">{fmtTime(e.starts_at)}{where ? ` · ${where}` : ""}{e.distance_km != null ? ` · ${km(e.distance_km)}` : ""}</span>
        <span className="flex items-center gap-2 shrink-0">
          {e.rating?.count > 0 && <span className="flex items-center gap-1"><Stars value={1} size={13} />{e.rating.average}</span>}
          {e.phase !== "past" && <span style={{ color: full ? "var(--danger)" : "var(--fg)" }}>{full ? "Full" : seats}</span>}
        </span>
      </div>
    </Link>
  );
}
