"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Empty, Field, Input, Spinner, Tabs, Tag, Textarea } from "./ui";
import { SecurityPanel } from "./SecurityPanel";

export function MeClient() {
  const { user, refresh } = useAuth();
  const sp = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const tab = sp.get("tab") || "overview";
  const [clubs, setClubs] = useState<any[] | null>(null);
  const [regs, setRegs] = useState<any[] | null>(null);
  const [notes, setNotes] = useState<any[] | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [p, setP] = useState<any>(null);

  const loadNotes = useCallback(() => api("/notifications").then(setNotes).catch(() => setNotes([])), []);
  useEffect(() => { api("/users/me/memberships").then(setClubs); api("/users/me/registrations").then(setRegs); loadNotes(); api("/auth/sessions").then(setSessions); api("/auth/login-history").then(setHistory); }, [loadNotes]);
  useEffect(() => { if (user) setP({ full_name: user.full_name, bio: user.bio, institution: user.institution || "", department: user.department || "", class_year: user.class_year || "", skills: (user.skills || []).join(", "), profile_public: user.profile_public, show_email: user.show_email }); }, [user]);
  const setTab = (t: string) => router.replace(`/me?tab=${t}`);
  const unread = notes?.filter((n) => !n.read).length || 0;

  const save = async () => {
    try { await api("/users/me", { method: "PATCH", body: { ...p, skills: p.skills.split(",").map((s: string) => s.trim()).filter(Boolean), institution: p.institution || null, department: p.department || null, class_year: p.class_year || null } }); await refresh(); toast("Profile saved"); }
    catch (e: any) { toast(e.message, "err"); }
  };
  if (!user) return null;
  return (
    <div className="wrap py-16">
      <h1 className="display h-xl">{user.full_name}</h1>
      <p className="muted mt-2">@{user.username}{!user.email_verified && <> · <span style={{ color: "var(--danger)" }}>Email not verified. Check your inbox.</span></>}</p>
      <div className="mt-10"><Tabs id="me" value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview" }, { id: "notifications", label: "Notifications", badge: unread || undefined }, { id: "profile", label: "Profile" }, { id: "security", label: "Security" }]} /></div>

      {tab === "overview" && (
        <div className="mt-12 grid grid-cols-1 gap-14 lg:grid-cols-2">
          <section><h2 className="display h-md mb-5">Your clubs</h2>
            {!clubs ? <Spinner /> : clubs.filter((c) => c.status !== "former").length === 0 ? <Empty title="No clubs yet" action={<Button href="/discover" variant="primary">Find clubs</Button>} /> :
              <ul className="divide-y divide-[var(--line)] border-y border-line">{clubs.filter((c) => c.status !== "former").map((c) => (
                <li key={c.club.slug} className="py-4 flex items-center justify-between gap-4"><div><Link className="display h-md link" href={`/c/${c.club.slug}`}>{c.club.name}</Link><p className="muted text-sm">{c.role}</p></div>
                  <div className="flex items-center gap-3">{c.status !== "active" && <Tag>{c.status}</Tag>}{c.status === "active" && c.role !== "Member" && c.role !== "Volunteer" && <Button size="sm" href={`/manage/${c.club.slug}`}>Manage</Button>}</div></li>))}</ul>}
          </section>
          <section><h2 className="display h-md mb-5">Your tickets</h2>
            {!regs ? <Spinner /> : regs.length === 0 ? <Empty title="No tickets" body="Register for an event and your QR ticket appears here." action={<Button href="/discover">Browse events</Button>} /> :
              <ul className="divide-y divide-[var(--line)] border-y border-line">{regs.map((r) => (
                <li key={r.id} className="py-4 flex items-center justify-between gap-4"><div><Link className="display h-md link" href={`/e/${r.event.slug}`}>{r.event.title}</Link><p className="muted text-sm">{fmtDateTime(r.event.starts_at)}</p></div>
                  <Tag>{r.checked_in ? "Checked in" : r.status}</Tag></li>))}</ul>}
          </section>
        </div>
      )}

      {tab === "notifications" && (
        <div className="mt-10 max-w-2xl">
          {unread > 0 && <Button size="sm" onClick={async () => { await api("/notifications/read-all", { method: "POST" }); loadNotes(); }}>Mark all read</Button>}
          {!notes ? <Spinner /> : notes.length === 0 ? <Empty title="You're all caught up" /> :
            <ul className="mt-6 divide-y divide-[var(--line)] border-y border-line">{notes.map((n) => (
              <li key={n.id} className="py-4 flex gap-4 justify-between" style={{ opacity: n.read ? .6 : 1 }}>
                <div><p className="font-semibold">{n.title}</p>{n.body && <p className="muted text-sm">{n.body}</p>}<p className="muted text-xs mt-1">{fmtDateTime(n.created_at)}</p></div>
                <div className="flex gap-3 items-start text-sm">{n.link && <Link className="link" href={n.link}>Open</Link>}{!n.read && <button className="link muted" onClick={async () => { await api(`/notifications/${n.id}/read`, { method: "POST" }); loadNotes(); }}>Mark read</button>}</div></li>))}</ul>}
        </div>
      )}

      {tab === "profile" && p && (
        <div className="mt-10 max-w-2xl space-y-6">
          <Field label="Full name"><Input value={p.full_name} onChange={(e) => setP({ ...p, full_name: e.target.value })} /></Field>
          <Field label="Bio"><Textarea maxLength={1000} value={p.bio} onChange={(e) => setP({ ...p, bio: e.target.value })} /></Field>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <Field label="Institution"><Input value={p.institution} onChange={(e) => setP({ ...p, institution: e.target.value })} /></Field>
            <Field label="Department"><Input value={p.department} onChange={(e) => setP({ ...p, department: e.target.value })} /></Field>
            <Field label="Class or year"><Input value={p.class_year} onChange={(e) => setP({ ...p, class_year: e.target.value })} /></Field></div>
          <Field label="Skills" hint="Comma separated"><Input value={p.skills} onChange={(e) => setP({ ...p, skills: e.target.value })} /></Field>
          <div className="space-y-2">
            <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={p.profile_public} onChange={(e) => setP({ ...p, profile_public: e.target.checked })} />Anyone can view my profile</label>
            <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={p.show_email} onChange={(e) => setP({ ...p, show_email: e.target.checked })} />Show my email on my profile</label></div>
          <Button variant="primary" onClick={save}>Save profile</Button>
        </div>
      )}

      {tab === "security" && (
        <div className="mt-10 grid grid-cols-1 gap-14 lg:grid-cols-2">
          <section><h2 className="display h-md mb-5">Signed-in devices</h2>
            <ul className="divide-y divide-[var(--line)] border-y border-line">{sessions.map((s) => (
              <li key={s.id} className="py-3 flex justify-between gap-4 text-sm"><div className="min-w-0"><p className="truncate">{s.user_agent || "Unknown device"}</p><p className="muted">{s.ip} · {fmtDate(s.created_at)}</p></div>
                {s.current ? <Tag>This device</Tag> : <button className="link muted" onClick={async () => { await api(`/auth/sessions/${s.id}`, { method: "DELETE" }); setSessions(await api("/auth/sessions")); }}>Sign out</button>}</li>))}</ul></section>
          <section><h2 className="display h-md mb-5">Recent sign-ins</h2>
            <ul className="divide-y divide-[var(--line)] border-y border-line">{history.slice(0, 10).map((h, i) => (
              <li key={i} className="py-3 flex justify-between gap-4 text-sm"><span>{h.ip}</span><span className="muted">{fmtDateTime(h.at)}</span><span style={{ color: h.success ? "var(--ok)" : "var(--danger)" }}>{h.success ? "Success" : "Failed"}</span></li>))}</ul></section>
        </div>
      )}
      {tab === "security" && (
        <div><SecurityPanel /></div>
      )}
    </div>
  );
}
