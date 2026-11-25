"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { bytes, fmtDateTime } from "@/lib/format";
import { Button, Spinner } from "../ui";
import type { Ctx } from "./ManageClient";

export function Meter({ label, used, max, fmt = (n: number) => String(n) }: { label: string; used: number; max: number | null; fmt?: (n: number) => string }) {
  const pct = max ? Math.min(100, (used / max) * 100) : 0;
  return (
    <div><div className="flex justify-between text-sm"><span className="muted">{label}</span><span>{fmt(used)} / {max === null ? "unlimited" : fmt(max)}</span></div>
      <div className="h-1.5 mt-2" style={{ background: "var(--bg3)" }}><div className="h-full transition-all duration-700" style={{ width: `${max ? pct : 6}%`, background: pct > 90 ? "var(--danger)" : "var(--accent)" }} /></div></div>
  );
}

/** Answers three questions: what happened, what needs attention, what can I do. */
export function Overview({ slug, usage, go }: Ctx) {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api(`/clubs/${slug}/dashboard`).then(setD); }, [slug]);
  if (!d) return <Spinner />;
  const L = usage.limits, U = usage.usage;
  const labels: Record<string, [string, string]> = { review_applications: ["Review applications", "members"], create_event: ["Create an event", "events"], create_post: ["Write a post", "posts"], send_announcement: ["Email your members", "email"] };
  return (
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-12">
        <section><h2 className="display h-md mb-4">Needs attention</h2>
          {d.attention?.pending_members > 0 ? <button onClick={() => go("members")} className="panel sheen w-full text-left p-5 flex justify-between items-center"><span><strong>{d.attention.pending_members}</strong> membership request{d.attention.pending_members > 1 ? "s" : ""} waiting</span><span style={{ color: "var(--accent)" }}>Review</span></button>
            : <p className="muted">Nothing is waiting on you.</p>}</section>
        {d.upcoming_events && <section><h2 className="display h-md mb-4">Upcoming events</h2>
          {d.upcoming_events.length ? <ul className="divide-y divide-[var(--line)] border-y border-line">{d.upcoming_events.map((e: any) => <li key={e.slug} className="py-3 flex justify-between gap-4"><Link className="link" href={`/e/${e.slug}`}>{e.title}</Link><span className="muted text-sm">{fmtDateTime(e.starts_at)}</span></li>)}</ul> : <p className="muted">No published events ahead.</p>}</section>}
        {d.recent?.registrations && <section><h2 className="display h-md mb-4">What happened</h2>
          {d.recent.registrations.length ? <ul className="divide-y divide-[var(--line)] border-y border-line text-sm">{d.recent.registrations.map((r: any, i: number) => <li key={i} className="py-2.5 flex justify-between gap-4"><span>{r.name} registered for {r.event}</span><span className="muted">{r.status}</span></li>)}</ul> : <p className="muted">No registrations yet.</p>}</section>}
      </div>
      <aside className="space-y-10">
        <section><h2 className="display h-md mb-4">What can I do</h2>
          <div className="flex flex-col gap-3">{(d.actions || []).map((a: string) => labels[a] && <Button key={a} onClick={() => go(labels[a][1])}>{labels[a][0]}</Button>)}</div></section>
        <section className="panel p-6 space-y-5"><h2 className="display h-md">Your plan</h2>
          <Meter label="Members" used={U.members} max={L.members} />
          <Meter label="Admin seats" used={U.admins} max={L.admins} />
          <Meter label="Active events" used={U.active_events} max={L.active_events} />
          <Meter label="Storage" used={U.storage_bytes} max={L.storage_mb === null ? null : L.storage_mb * 1048576} fmt={bytes} /></section>
      </aside>
    </div>
  );
}
