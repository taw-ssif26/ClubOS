"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select, Spinner, Tag } from "../ui";
import type { Ctx } from "./ManageClient";

const PERMS = ["club.settings", "members.view", "members.manage", "roles.manage", "events.manage", "registrations.manage", "attendance.manage", "forms.manage", "posts.manage", "comms.send", "analytics.view", "audit.view", "files.manage"];

export function Members({ slug, can, reload }: Ctx) {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [roles, setRoles] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [invite, setInvite] = useState("");
  const [nr, setNr] = useState({ name: "", rank: 30, permissions: [] as string[] });
  const manage = can("members.manage");

  const load = useCallback(() => {
    const p = new URLSearchParams(); if (q) p.set("q", q); if (status) p.set("status", status);
    api(`/clubs/${slug}/members?${p}`).then(setRows);
    api(`/clubs/${slug}/roles`).then(setRoles);
  }, [slug, q, status]);
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load]);

  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok); load(); reload(); } catch (e: any) { toast(e.message, "err"); } };
  const patch = (id: string, body: any, ok = "Updated") => run(() => api(`/clubs/${slug}/members/${id}`, { method: "PATCH", body }), ok);

  return (
    <div className="space-y-16">
      <section>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Search" className="flex-1 min-w-[200px]"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or username" /></Field>
          <Field label="Status"><Select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{["pending", "active", "suspended", "rejected", "former", "invited"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
          {manage && <a className="btn btn-sm" href={`/api/clubs/${slug}/members.csv`}>Export CSV</a>}
        </div>
        {!rows ? <Spinner /> : (
          <div className="mt-8 overflow-x-auto"><table className="t"><thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Joined</th>{manage && <th>Actions</th>}</tr></thead><tbody>
            {rows.map((m) => (
              <tr key={m.id}>
                <td><p className="font-semibold">{m.user.full_name}</p><p className="muted text-xs">@{m.user.username}{m.user.email ? ` · ${m.user.email}` : ""}</p>
                  {m.application && Object.keys(m.application).length > 0 && <details className="text-xs mt-1"><summary className="link muted cursor-pointer">Application</summary><pre className="whitespace-pre-wrap muted mt-1">{Object.entries(m.application).map(([k, v]) => `${k}: ${v}`).join("\n")}</pre></details>}</td>
                <td>{manage && m.status === "active" ? <Select className="!py-1" value={m.role.id} onChange={(e) => patch(m.id, { role_id: e.target.value }, "Role changed")}>{roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select> : m.role.name}</td>
                <td><Tag>{m.status}</Tag></td><td className="muted">{fmtDate(m.joined_at)}</td>
                {manage && <td><div className="flex gap-2 flex-wrap">
                  {m.status === "pending" && <><Button size="sm" variant="primary" onClick={() => patch(m.id, { status: "active" }, "Approved")}>Approve</Button><Button size="sm" onClick={() => patch(m.id, { status: "rejected" }, "Rejected")}>Reject</Button></>}
                  {m.status === "active" && <Button size="sm" onClick={() => patch(m.id, { status: "suspended" }, "Suspended")}>Suspend</Button>}
                  {m.status === "suspended" && <Button size="sm" onClick={() => patch(m.id, { status: "active" }, "Reinstated")}>Reinstate</Button>}
                  {["active", "suspended"].includes(m.status) && <Button size="sm" variant="danger" onClick={() => confirm(`Remove ${m.user.full_name}?`) && run(() => api(`/clubs/${slug}/members/${m.id}`, { method: "DELETE" }), "Removed")}>Remove</Button>}
                  <Button size="sm" onClick={() => { const n = prompt("Private note (only visible to member managers)", m.notes || ""); if (n !== null) patch(m.id, { notes: n }, "Note saved"); }}>{m.notes ? "Note ✓" : "Note"}</Button></div></td>}
              </tr>))}
          </tbody></table>{rows.length === 0 && <p className="muted py-8">No members match.</p>}</div>
        )}
        {manage && <div className="mt-10 flex gap-3 items-end max-w-md"><Field label="Invite by username" className="flex-1"><Input value={invite} onChange={(e) => setInvite(e.target.value.toLowerCase())} /></Field>
          <Button disabled={!invite} onClick={() => run(async () => { await api(`/clubs/${slug}/invites`, { method: "POST", body: { username: invite } }); setInvite(""); }, "Invitation sent")}>Invite</Button></div>}
      </section>

      {can("roles.manage") && (
        <section><h2 className="display h-lg">Roles</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ul className="divide-y divide-[var(--line)] border-y border-line">{roles.map((r) => (
              <li key={r.id} className="py-3 flex justify-between gap-4"><div><p className="font-semibold">{r.name} {r.is_system && <Tag>built in</Tag>}</p><p className="muted text-xs">{r.permissions.includes("*") ? "Everything" : r.permissions.join(", ") || "No permissions"}</p></div>
                {!r.is_system && <Button size="sm" variant="danger" onClick={() => run(() => api(`/clubs/${slug}/roles/${r.id}`, { method: "DELETE" }), "Role deleted")}>Delete</Button>}</li>))}</ul>
            <div className="panel p-6 space-y-4"><p className="font-semibold">New custom role</p>
              <Field label="Name, e.g. Media Secretary"><Input value={nr.name} onChange={(e) => setNr({ ...nr, name: e.target.value })} /></Field>
              <Field label="Rank (1 to 89). Higher ranks can manage lower ones." ><Input type="number" min={1} max={89} value={nr.rank} onChange={(e) => setNr({ ...nr, rank: Number(e.target.value) })} /></Field>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">{PERMS.filter((p) => can(p)).map((p) => <label key={p} className="flex items-center gap-2"><input className="check" type="checkbox" checked={nr.permissions.includes(p)} onChange={(e) => setNr({ ...nr, permissions: e.target.checked ? [...nr.permissions, p] : nr.permissions.filter((x) => x !== p) })} />{p}</label>)}</div>
              <p className="muted text-xs">You can only grant permissions you hold. Roles ranked 50 or higher use an admin seat.</p>
              <Button variant="primary" disabled={nr.name.length < 2} onClick={() => run(async () => { await api(`/clubs/${slug}/roles`, { method: "POST", body: nr }); setNr({ name: "", rank: 30, permissions: [] }); }, "Role created")}>Create role</Button></div>
          </div>
        </section>
      )}
    </div>
  );
}
