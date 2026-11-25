"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fmtDateTime, fromLocalInput, toLocalInput } from "@/lib/format";
import { uploadImage } from "@/lib/upload";
import { useToast } from "@/lib/toast";
import { FieldBuilder } from "../FieldBuilder";
import { LocationPicker, locPayload } from "../LocationPicker";
import { Button, Field, Input, Select, Spinner, Tag, Textarea, Upgrade } from "../ui";
import type { Ctx } from "./ManageClient";

const blank = () => ({ slug: "", title: "", description: "", venue: "", location_mode: "onsite", place: "", address: "", latitude: null as number | null, longitude: null as number | null, online_url: "", starts_at: "", ends_at: "", capacity: "", visibility: "public", status: "draft", registration_closes_at: "", banner_url: "", registration_fields: [] as any[] });

function Scanner({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [code, setCode] = useState("");
  const [res, setRes] = useState<{ ok: boolean; text: string } | null>(null);
  const [cam, setCam] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const last = useRef({ code: "", at: 0 });

  const submit = async (c: string) => {
    try { const r = await api(`/events/${slug}/checkin`, { method: "POST", body: { ticket_code: c } }); setRes({ ok: true, text: `${r.name} is checked in` }); onDone(); }
    catch (e: any) { setRes({ ok: false, text: `${e.message}${e.detail?.name ? `: ${e.detail.name}` : ""}` }); }
    setCode("");
  };
  useEffect(() => {
    if (!cam) return;
    const BD = (window as any).BarcodeDetector;
    let stream: MediaStream | null = null, timer = 0, dead = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (dead || !video.current) return;
        video.current.srcObject = stream; await video.current.play();
        const det = new BD({ formats: ["qr_code"] });
        timer = window.setInterval(async () => {
          try {
            const found = await det.detect(video.current!);
            const v = found[0]?.rawValue;
            if (v && (v !== last.current.code || Date.now() - last.current.at > 3000)) { last.current = { code: v, at: Date.now() }; submit(v); }
          } catch {}
        }, 350);
      } catch { setRes({ ok: false, text: "Camera unavailable. Type or scan the code instead." }); setCam(false); }
    })();
    return () => { dead = true; clearInterval(timer); stream?.getTracks().forEach((t) => t.stop()); };
  }, [cam]);

  const supported = typeof window !== "undefined" && "BarcodeDetector" in window;
  return (
    <div className="panel p-6 space-y-4">
      <p className="display h-md">Check-in</p>
      <form onSubmit={(e) => { e.preventDefault(); if (code.trim()) submit(code.trim()); }} className="flex gap-3">
        <Input autoFocus aria-label="Ticket code" placeholder="Scan or type ticket code" value={code} onChange={(e) => setCode(e.target.value)} />
        <Button type="submit" variant="primary">Check in</Button>
      </form>
      {supported && <Button size="sm" onClick={() => setCam(!cam)}>{cam ? "Stop camera" : "Scan with camera"}</Button>}
      {cam && <video ref={video} muted playsInline className="w-full max-w-sm border border-line" style={{ borderRadius: "var(--r)" }} />}
      {res && <p role="status" className="p-3 text-sm font-semibold" style={{ borderLeft: `3px solid ${res.ok ? "var(--ok)" : "var(--danger)"}`, background: "var(--bg3)" }}>{res.text}</p>}
      <p className="muted text-xs">A USB or Bluetooth barcode scanner works too: it types the code and presses Enter.</p>
    </div>
  );
}

export function Events({ slug, usage, can }: Ctx) {
  const toast = useToast();
  const [list, setList] = useState<any[] | null>(null);
  const [f, setF] = useState<any>(null);
  const [regs, setRegs] = useState<any[]>([]);
  const [att, setAtt] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [upsell, setUpsell] = useState("");
  const full = can("events.manage");

  const load = () => api(`/clubs/${slug}/events?include_past=true`).then(setList);
  useEffect(() => { load(); }, [slug]);
  const loadRegs = (s: string) => { api(`/events/${s}/attendance`).then(setAtt).catch(() => {}); if (can("registrations.manage")) api(`/events/${s}/registrations`).then(setRegs).catch(() => setRegs([])); };

  const open = async (s: string) => {
    const e = await api(`/events/${s}`);
    setF({ ...blank(), ...e, capacity: e.capacity ?? "", starts_at: toLocalInput(e.starts_at), ends_at: toLocalInput(e.ends_at), registration_closes_at: toLocalInput(e.registration_closes_at), banner_url: e.banner_url || "", location_mode: e.location?.mode || "onsite", place: e.location?.place || "", address: e.location?.address || "", latitude: e.location?.latitude ?? null, longitude: e.location?.longitude ?? null, online_url: e.online_url || "", description: e.description || "" });
    setUpsell(""); loadRegs(s);
  };
  const save = async () => {
    setSaving(true); setUpsell("");
    const body: any = { title: f.title, description: f.description, venue: f.venue, ...locPayload(f), starts_at: fromLocalInput(f.starts_at), ends_at: fromLocalInput(f.ends_at),
      capacity: f.capacity === "" ? null : Number(f.capacity), visibility: f.visibility, status: f.status, registration_closes_at: fromLocalInput(f.registration_closes_at), registration_fields: f.registration_fields, banner_url: f.banner_url || null, online_url: f.online_url || null };
    try {
      const e = await api(f.slug ? `/events/${f.slug}` : `/clubs/${slug}/events`, { method: f.slug ? "PATCH" : "POST", body });
      toast("Event saved"); await load(); await open(e.slug);
    } catch (x: any) { if (x instanceof ApiError && x.status === 402) setUpsell(x.message); else toast(x.message, "err"); } finally { setSaving(false); }
  };

  return (
    <div className="grid grid-cols-1 gap-12 xl:grid-cols-[320px_1fr]">
      <section>
        <div className="flex justify-between items-center mb-5"><h2 className="display h-md">Events</h2>{full && <Button size="sm" variant="primary" onClick={() => { setF(blank()); setRegs([]); setAtt(null); setUpsell(""); }}>New</Button>}</div>
        {!list ? <Spinner /> : list.length === 0 ? <p className="muted">No events yet.</p> : <ul className="divide-y divide-[var(--line)] border-y border-line">{list.map((e) => (
          <li key={e.slug}><button onClick={() => open(e.slug)} className="w-full text-left py-3 px-1 hover:bg-[var(--bg2)] transition-colors" style={f?.slug === e.slug ? { background: "var(--bg2)" } : undefined}>
            <p className="font-semibold">{e.title}</p><p className="muted text-xs">{fmtDateTime(e.starts_at)} · {e.registered}{e.capacity ? `/${e.capacity}` : ""} <Tag>{e.status}</Tag></p></button></li>))}</ul>}
      </section>

      {f ? (
        <div className="space-y-12 min-w-0">
          {f.slug && <div className="grid grid-cols-1 gap-6 lg:grid-cols-2"><Scanner slug={f.slug} onDone={() => loadRegs(f.slug)} />
            {att && <div className="panel p-6"><p className="display h-md">Attendance</p><div className="grid grid-cols-3 gap-3 mt-5 text-center">
              {[["Registered", att.confirmed], ["Checked in", att.checked_in], ["Waitlist", att.waitlisted]].map(([l, v]) => <div key={l as string}><p className="display" style={{ fontSize: "2.6rem", lineHeight: 1, color: "var(--accent)" }}>{v}</p><p className="muted text-sm">{l}</p></div>)}</div>
              {att.attendance_rate != null && <p className="muted text-sm mt-5">{Math.round(att.attendance_rate * 100)}% of registered attendees have arrived.</p>}</div>}</div>}

          {full && (
            <section className="panel p-6 space-y-6">
              <h2 className="display h-md">{f.slug ? "Edit event" : "New event"}</h2>
              <Field label="Title"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
              <Field label="Description"><Textarea style={{ minHeight: "9rem" }} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <Field label="Starts"><Input type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
                <Field label="Ends (optional)"><Input type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} /></Field>
                <Field label="Venue"><Input value={f.venue} onChange={(e) => setF({ ...f, venue: e.target.value })} /></Field>
                <Field label="Seats (empty = unlimited)"><Input type="number" min={1} value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></Field>
                <Field label="Registration closes (default: start)"><Input type="datetime-local" value={f.registration_closes_at} onChange={(e) => setF({ ...f, registration_closes_at: e.target.value })} /></Field>
                <Field label="Visibility"><Select value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value })}><option value="public">Public</option><option value="members">Club members</option><option value="private">Managers only</option></Select></Field>
                <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="draft">Draft</option><option value="published">Published</option><option value="cancelled">Cancelled</option></Select></Field>
                </div>
              <div className="border-t border-line pt-6 space-y-5"><p className="font-semibold">Location</p>
                <LocationPicker value={f} onChange={(v) => setF({ ...f, ...v })} />
                {f.location_mode !== "onsite" && <Field label="Online link (Zoom, Meet...)" hint="Shown only to registered attendees and organizers."><Input type="url" placeholder="https://" value={f.online_url} onChange={(e) => setF({ ...f, online_url: e.target.value })} /></Field>}</div>
              <Field label="Banner image" hint="PNG, JPEG or WebP. Keep it small, a few hundred KB."><div className="flex items-center gap-4">{f.banner_url && <img src={f.banner_url} alt="" className="h-14 w-24 object-cover border border-line" />}
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={async (e) => { const file = e.target.files?.[0]; if (!file) return; try { setF({ ...f, banner_url: await uploadImage(slug, file) }); } catch (x: any) { toast(x.message, "err"); } }} /></div></Field>
              <div><p className="font-semibold mb-3">Registration questions</p><p className="muted text-sm mb-4">Name and email come from the member&apos;s account. Add only what you need to ask.</p>
                <FieldBuilder fields={f.registration_fields} onChange={(x) => setF({ ...f, registration_fields: x })} canConditions={!!usage.limits.conditional_logic} />
                {!usage.limits.conditional_logic && <p className="muted text-xs mt-3">Conditional questions and waitlists are included in Pro.</p>}</div>
              {upsell && <Upgrade message={upsell} />}
              <Button variant="primary" loading={saving} disabled={!f.title || !f.starts_at} onClick={save}>{f.slug ? "Save changes" : "Create event"}</Button>
            </section>)}

          {f.slug && can("registrations.manage") && (
            <section><div className="flex justify-between items-center mb-5"><h2 className="display h-md">Registrations</h2><a className="btn btn-sm" href={`/api/events/${f.slug}/registrations.csv`}>Export CSV</a></div>
              <div className="overflow-x-auto"><table className="t"><thead><tr><th>Name</th><th>Status</th><th>Ticket</th><th>Arrived</th><th /></tr></thead><tbody>
                {regs.map((r) => <tr key={r.id}><td><p className="font-semibold">{r.user.full_name}</p><p className="muted text-xs">{r.user.email}</p></td><td><Tag>{r.status}</Tag></td><td className="text-xs">{r.ticket_code}</td><td className="muted">{r.checked_in_at ? "Yes" : ""}</td>
                  <td>{r.status === "confirmed" && !r.checked_in_at && <Button size="sm" onClick={async () => { try { await api(`/events/${f.slug}/checkin/manual/${r.id}`, { method: "POST" }); loadRegs(f.slug); } catch (x: any) { toast(x.message, "err"); } }}>Check in</Button>}</td></tr>)}</tbody></table>
                {regs.length === 0 && <p className="muted py-8">No registrations yet.</p>}</div></section>)}
        </div>
      ) : <p className="muted">Select an event to manage registrations and check-in, or create a new one.</p>}
    </div>
  );
}
