"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fromLocalInput } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select, Textarea, Upgrade } from "../ui";
import type { Ctx } from "./ManageClient";

const AUD = [["all_members", "All active members"], ["role", "Everyone with a role"], ["event_registered", "Registered for an event"], ["event_checked_in", "Attended an event"], ["event_not_checked_in", "Registered but didn't show up"]];
const VARS = ["first_name", "full_name", "club_name", "event_name"];

export function Email({ slug, usage }: Ctx) {
  const toast = useToast();
  const [events, setEvents] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [hist, setHist] = useState<any[]>([]);
  const [f, setF] = useState({ type: "all_members", event_slug: "", role_id: "", subject: "", body: "", send_at: "" });
  const [busy, setBusy] = useState(false);
  const enabled = usage.limits.bulk_email;
  const load = () => api(`/clubs/${slug}/communications`).then(setHist).catch(() => {});
  useEffect(() => { if (!enabled) return; api(`/clubs/${slug}/events?include_past=true`).then(setEvents); api(`/clubs/${slug}/roles`).then(setRoles); load(); }, [slug, enabled]);
  if (!enabled) return <div className="max-w-2xl space-y-6"><h2 className="display h-lg">Email your members</h2><p className="lede">Send personalized, segmented and scheduled email, for example &quot;everyone who registered but didn&apos;t show up&quot;. Registration confirmations are always free and automatic.</p><Upgrade feature="bulk, personalized and scheduled email" message="Bulk email is a Pro feature." /></div>;
  const needsEvent = f.type.startsWith("event_");
  const send = async () => {
    setBusy(true);
    try { const r = await api(`/clubs/${slug}/communications`, { method: "POST", body: { subject: f.subject, body: f.body, send_at: fromLocalInput(f.send_at), audience: { type: f.type, event_slug: needsEvent ? f.event_slug : null, role_id: f.type === "role" ? f.role_id : null } } });
      toast(`${r.queued} email${r.queued > 1 ? "s" : ""} queued`); setF({ ...f, subject: "", body: "" }); load(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.3fr_1fr]">
      <section className="panel p-6 space-y-5">
        <h2 className="display h-md">New message</h2>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Send to"><Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{AUD.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
          {needsEvent && <Field label="Event"><Select value={f.event_slug} onChange={(e) => setF({ ...f, event_slug: e.target.value })}><option value="">Choose…</option>{events.map((e) => <option key={e.slug} value={e.slug}>{e.title}</option>)}</Select></Field>}
          {f.type === "role" && <Field label="Role"><Select value={f.role_id} onChange={(e) => setF({ ...f, role_id: e.target.value })}><option value="">Choose…</option>{roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select></Field>}
        </div>
        <Field label="Subject"><Input value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} /></Field>
        <Field label="Message"><Textarea style={{ minHeight: "12rem" }} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
        <div className="flex flex-wrap gap-2 items-center text-sm"><span className="muted">Insert:</span>{VARS.map((v) => <button key={v} type="button" className="tag" onClick={() => setF({ ...f, body: `${f.body}{{${v}}}` })}>{`{{${v}}}`}</button>)}</div>
        <Field label="Schedule (optional)" hint="Leave empty to send right away"><Input type="datetime-local" value={f.send_at} onChange={(e) => setF({ ...f, send_at: e.target.value })} /></Field>
        <Button variant="primary" loading={busy} disabled={!f.subject || !f.body || (needsEvent && !f.event_slug) || (f.type === "role" && !f.role_id)} onClick={send}>{f.send_at ? "Schedule" : "Send now"}</Button>
      </section>
      <section><h2 className="display h-md mb-4">Sent</h2>
        {hist.length === 0 ? <p className="muted">Nothing sent yet.</p> : <ul className="divide-y divide-[var(--line)] border-y border-line text-sm">{hist.map((h, i) => <li key={i} className="py-2.5 flex justify-between gap-4"><span className="truncate">{h.subject}</span><span className="muted shrink-0">{h.count} · {h.status}</span></li>)}</ul>}</section>
    </div>
  );
}
