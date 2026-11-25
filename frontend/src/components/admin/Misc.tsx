"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select, Spinner, Tag } from "../ui";

export function ModerationAdmin() {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [status, setStatus] = useState("published");
  const [reported, setReported] = useState(true);
  const load = () => api(`/admin/reviews?status=${status}&reported=${reported}`).then(setRows);
  useEffect(() => { setRows(null); load(); }, [status, reported]);
  const act = async (id: string, a: string) => { try { await api(`/admin/reviews/${id}/${a}`, { method: "POST" }); toast("Done"); load(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="space-y-8">
      <div className="flex gap-6 items-end flex-wrap"><Field label="Show"><Select value={status} onChange={(e) => setStatus(e.target.value)}><option value="published">Published</option><option value="hidden">Hidden</option></Select></Field>
        <label className="flex items-center gap-2 pb-2"><input className="check" type="checkbox" checked={reported} onChange={(e) => setReported(e.target.checked)} />Only reported</label></div>
      {!rows ? <Spinner /> : rows.length === 0 ? <p className="muted">Nothing to review.</p> : (
        <ul className="divide-y divide-[var(--line)] border-y border-line">{rows.map((r) => (
          <li key={r.id} className="py-4 flex justify-between gap-6 flex-wrap"><div className="max-w-2xl"><p className="text-sm muted">{r.user} on {r.club} · {r.type} · {"★".repeat(r.rating)} · {fmtDate(r.created_at)} {r.reports > 0 && <Tag>{r.reports} report{r.reports > 1 ? "s" : ""}</Tag>}</p>{r.title && <p className="font-semibold">{r.title}</p>}<p>{r.body}</p></div>
            <div className="flex gap-2 items-start">{r.status === "published" ? <Button size="sm" onClick={() => act(r.id, "hide")}>Hide</Button> : <Button size="sm" onClick={() => act(r.id, "unhide")}>Restore</Button>}<Button size="sm" variant="danger" onClick={() => confirm("Delete permanently?") && act(r.id, "delete")}>Delete</Button></div></li>))}</ul>)}
    </div>
  );
}

export function ClubsAdmin() {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("pending");
  const load = () => api(`/admin/clubs?q=${encodeURIComponent(q)}${status ? `&status=${status}` : ""}`).then(setRows);
  useEffect(() => { setRows(null); const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q, status]);
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok); load(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-5 items-end">
        <Field label="Search clubs" className="min-w-[240px]"><Input value={q} onChange={(e) => setQ(e.target.value)} /></Field>
        <Field label="Show"><Select value={status} onChange={(e) => setStatus(e.target.value)}><option value="pending">Awaiting approval</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="">All</option></Select></Field>
      </div>
      {!rows ? <Spinner /> : rows.length === 0 ? <p className="muted">{status === "pending" ? "No clubs are waiting for approval." : "No clubs match."}</p> : (
        <div className="space-y-4">{rows.map((c) => (
          <div key={c.slug} className="panel p-5 flex flex-wrap gap-6 justify-between">
            <div className="min-w-0 max-w-2xl">
              <p className="font-semibold"><a className="link" href={`/c/${c.slug}`}>{c.name}</a> <Tag>{c.status}</Tag> {c.verified && <Tag>verified</Tag>} <Tag>{c.plan}</Tag></p>
              <p className="muted text-xs mt-1">{c.slug} · {c.category} · {c.members} member{c.members === 1 ? "" : "s"} · created {fmtDate(c.created_at)}</p>
              {c.description && <p className="mt-3 text-sm whitespace-pre-line">{c.description}</p>}
              {c.owner && <p className="muted text-xs mt-3">Requested by <strong>{c.owner.name}</strong> ({c.owner.email}) · account {c.owner.account_age_days} day{c.owner.account_age_days === 1 ? "" : "s"} old · {c.owner.clubs_created} club{c.owner.clubs_created === 1 ? "" : "s"} created · email {c.owner.verified ? "verified" : "NOT verified"}</p>}
              {c.status_note && <p className="text-xs mt-2" style={{ color: "var(--danger)" }}>Reason given: {c.status_note}</p>}
            </div>
            <div className="flex gap-2 flex-wrap items-start">
              {c.status !== "approved" && <Button size="sm" variant="primary" onClick={() => act(() => api(`/admin/clubs/${c.slug}/approve`, { method: "POST" }), "Approved")}>Approve</Button>}
              {c.status !== "rejected" && <Button size="sm" variant="danger" onClick={() => { const r = prompt("Reason (the owner will see this):"); if (r && r.trim().length >= 3) act(() => api(`/admin/clubs/${c.slug}/reject`, { method: "POST", body: { reason: r } }), "Rejected"); }}>Reject</Button>}
              {c.status === "approved" && !c.verified && <Button size="sm" onClick={() => act(() => api(`/admin/clubs/${c.slug}/verify`, { method: "POST" }), "Verified")}>Verify</Button>}
              {c.status === "approved" && <Select aria-label="Set plan" className="!w-auto !py-1" value="" onChange={(e) => e.target.value && act(() => api(`/admin/clubs/${c.slug}/plan`, { method: "POST", body: { plan: e.target.value, months: e.target.value === "free" ? 1 : Number(prompt("How many months?", "1") || 1) } }), "Plan updated")}><option value="">Set plan…</option>{["free", "pro", "organization", "enterprise"].map((p) => <option key={p}>{p}</option>)}</Select>}
            </div>
          </div>))}</div>)}
    </div>
  );
}

export function UsersAdmin() {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [q, setQ] = useState("");
  const load = () => api(`/admin/users?q=${encodeURIComponent(q)}`).then(setRows);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q]);
  const act = async (id: string, a: string) => { try { await api(`/admin/users/${id}/${a}`, { method: "POST" }); toast("Done"); load(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="space-y-8"><Field label="Search users" className="max-w-md"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, username or email" /></Field>
      {!rows ? <Spinner /> : <div className="overflow-x-auto"><table className="t"><thead><tr><th>User</th><th>Status</th><th>Joined</th><th /></tr></thead><tbody>{rows.map((u) => (
        <tr key={u.id}><td><p className="font-semibold">{u.full_name}</p><p className="muted text-xs">@{u.username} · {u.email}</p></td><td>{u.admin && <Tag>admin</Tag>} {!u.verified && <Tag>unverified</Tag>} {!u.active && <Tag>suspended</Tag>}</td><td className="muted">{fmtDate(u.created_at)}</td>
          <td>{!u.admin && (u.active ? <Button size="sm" variant="danger" onClick={() => confirm(`Suspend ${u.username}? Their sessions end immediately.`) && act(u.id, "suspend")}>Suspend</Button> : <Button size="sm" onClick={() => act(u.id, "unsuspend")}>Reinstate</Button>)}</td></tr>))}</tbody></table></div>}</div>
  );
}
