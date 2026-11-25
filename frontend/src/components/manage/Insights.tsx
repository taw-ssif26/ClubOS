"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDateTime, fmtDate } from "@/lib/format";
import { Spinner, Upgrade } from "../ui";
import type { Ctx } from "./ManageClient";

export function Analytics({ slug }: Ctx) {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api(`/clubs/${slug}/analytics`).then(setD); }, [slug]);
  if (!d) return <Spinner />;
  const a = d.advanced, max = a ? Math.max(1, ...a.member_growth.map((m: any) => m.total)) : 1;
  return (
    <div className="space-y-14">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">{[["Members", d.basic.members], ["Events", d.basic.events], ["Registrations", d.basic.registrations]].map(([l, v]) => (
        <div key={l as string} className="panel p-6"><p className="display" style={{ fontSize: "3.4rem", lineHeight: 1, color: "var(--accent)" }}>{v}</p><p className="muted mt-2">{l}</p></div>))}</div>
      {!a ? <Upgrade feature="member growth, retention and per-event performance" message="Advanced analytics is a Pro feature." /> : (<>
        <section><h2 className="display h-md mb-6">Member growth {a.retention != null && <span className="muted text-base" style={{ fontFamily: "var(--font-body)" }}>· {Math.round(a.retention * 100)}% retention</span>}</h2>
          <div className="flex items-end gap-2 h-48 border-b border-line">{a.member_growth.map((m: any) => (
            <div key={m.month} className="flex-1 min-w-[18px] flex flex-col items-center justify-end h-full group" title={`${m.month}: ${m.total} members (+${m.joined})`}>
              <span className="text-xs opacity-0 group-hover:opacity-100 mb-1">{m.total}</span><div className="w-full transition-all duration-700" style={{ height: `${(m.total / max) * 100}%`, background: "var(--accent)", minHeight: 3 }} /></div>))}</div>
          <div className="flex gap-2 mt-2">{a.member_growth.map((m: any) => <span key={m.month} className="flex-1 min-w-[18px] text-[10px] muted text-center">{m.month.slice(5)}</span>)}</div></section>
        <section><h2 className="display h-md mb-6">Event performance</h2><div className="overflow-x-auto"><table className="t"><thead><tr><th>Event</th><th>Registered</th><th>Attended</th><th>Attendance</th><th>Fill</th><th>Waitlist</th></tr></thead><tbody>
          {a.events.map((e: any) => <tr key={e.slug}><td>{e.title}<p className="muted text-xs">{fmtDateTime(e.starts_at)}</p></td><td>{e.registered}</td><td>{e.attended}</td><td>{e.attendance_rate != null ? `${Math.round(e.attendance_rate * 100)}%` : "–"}</td><td>{e.fill_rate != null ? `${Math.round(e.fill_rate * 100)}%` : "–"}</td><td>{e.waitlisted}</td></tr>)}</tbody></table></div></section></>)}
    </div>
  );
}

export function Activity({ slug }: Ctx) {
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => { api(`/clubs/${slug}/audit`).then(setRows); }, [slug]);
  if (!rows) return <Spinner />;
  return <ul className="divide-y divide-[var(--line)] border-y border-line text-sm max-w-3xl">{rows.map((r, i) => <li key={i} className="py-2.5 flex justify-between gap-4"><span><strong>{r.actor || "system"}</strong> {r.action}{r.target ? ` · ${r.target}` : ""}</span><span className="muted shrink-0">{fmtDate(r.at, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true })}</span></li>)}</ul>;
}
