"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { Button, Spinner, Tabs, Tag } from "../ui";
import { ContentEditor, OffersEditor, PlansEditor } from "./Editors";
import { ClubsAdmin, ModerationAdmin, UsersAdmin } from "./Misc";

function Overview({ go }: { go: (t: string) => void }) {
  const toast = useToast();
  const [s, setS] = useState<any>(null);
  const [reqs, setReqs] = useState<any[]>([]);
  const [log, setLog] = useState<any[]>([]);
  const [sys, setSys] = useState<any>(null);
  const load = () => { api("/admin/stats").then(setS); api("/admin/upgrade-requests").then(setReqs); api("/admin/audit?limit=15").then(setLog); api("/admin/system").then(setSys).catch(() => {}); };
  useEffect(load, []);
  const decide = async (id: string, what: "approve" | "reject") => { try { await api(`/admin/upgrade-requests/${id}/${what}`, { method: "POST", body: what === "reject" ? { note: prompt("Reason (shown to the club)") || "" } : undefined }); toast(what === "approve" ? "Plan activated" : "Rejected"); load(); } catch (e: any) { toast(e.message, "err"); } };
  if (!s) return <Spinner />;
  return (
    <div className="space-y-14">
      <div className="grid grid-cols-1 gap-4 grid-cols-2 lg:grid-cols-4">{[["Users", s.users], ["Clubs", s.clubs], ["Events", s.events], ["Registrations", s.registrations], ["Reviews", s.reviews], ["Reported reviews", s.reported_reviews], ["Emails pending", s.emails_pending], ["Emails failed", s.emails_failed]].map(([l, v]) => (
        <div key={l as string} className="panel p-5"><p className="display" style={{ fontSize: "2.6rem", lineHeight: 1, color: (l === "Emails failed" || l === "Reported reviews") && (v as number) > 0 ? "var(--danger)" : "var(--accent)" }}>{v}</p><p className="muted text-sm mt-1">{l}</p></div>))}</div>
      {s.pending_clubs > 0 && <button onClick={() => go("clubs")} className="panel sheen w-full text-left p-5 flex justify-between items-center" style={{ borderColor: "var(--accent)" }}><span><strong>{s.pending_clubs}</strong> club{s.pending_clubs > 1 ? "s" : ""} awaiting your approval</span><span style={{ color: "var(--accent)" }}>Review</span></button>}
      {sys && (
        <section><h2 className="display h-md mb-4">System check</h2>
          {sys.warnings.length === 0 ? <p className="muted">Everything looks correctly configured. Media: {sys.media_backend}, email: {sys.email_provider}, {sys.uploads} uploaded file{sys.uploads === 1 ? "" : "s"}.</p>
            : <ul className="space-y-2">{sys.warnings.map((w: string, i: number) => <li key={i} className="panel p-4 text-sm" style={{ borderColor: "var(--danger)" }}>{w}</li>)}</ul>}</section>)}
      <section><h2 className="display h-md mb-5">Upgrade requests {reqs.length > 0 && <Tag>{reqs.length} pending</Tag>}</h2>
        {reqs.length === 0 ? <p className="muted">No pending requests. Clubs by plan: {Object.entries(s.clubs_by_plan).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}.</p> :
          <div className="overflow-x-auto"><table className="t"><thead><tr><th>Club</th><th>Plan</th><th>Contact</th><th>Requested</th><th /></tr></thead><tbody>{reqs.map((r) => (
            <tr key={r.id}><td><p className="font-semibold">{r.club.name}</p><p className="muted text-xs">now {r.club.plan} · by {r.requested_by}</p></td><td>{r.plan_key} × {r.months} mo</td><td>{r.contact}{r.message && <p className="muted text-xs">{r.message}</p>}</td><td className="muted">{fmtDate(r.created_at)}</td>
              <td><div className="flex gap-2"><Button size="sm" variant="primary" onClick={() => decide(r.id, "approve")}>Confirm payment and activate</Button><Button size="sm" onClick={() => decide(r.id, "reject")}>Reject</Button></div></td></tr>))}</tbody></table></div>}</section>
      <section><h2 className="display h-md mb-5">Recent platform changes</h2>
        <ul className="divide-y divide-[var(--line)] border-y border-line text-sm max-w-3xl">{log.map((r, i) => <li key={i} className="py-2.5 flex justify-between gap-4"><span><strong>{r.actor}</strong> {r.action}{r.target ? ` · ${r.target}` : ""}</span><span className="muted">{fmtDateTime(r.at)}</span></li>)}</ul></section>
    </div>
  );
}

export function AdminClient() {
  const [tab, setTab] = useState("overview");
  return (
    <div className="wrap py-14">
      <p className="muted">Platform</p><h1 className="display h-xl">Super admin</h1>
      <div className="mt-10"><Tabs id="admin" value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview" }, { id: "content", label: "Page content" }, { id: "plans", label: "Plans and pricing" }, { id: "offers", label: "Offers" }, { id: "moderation", label: "Reviews" }, { id: "clubs", label: "Clubs" }, { id: "users", label: "Users" }]} /></div>
      <div className="mt-10">
        {tab === "overview" && <Overview go={setTab} />}
        {tab === "content" && <ContentEditor />}
        {tab === "plans" && <PlansEditor />}
        {tab === "offers" && <OffersEditor />}
        {tab === "moderation" && <ModerationAdmin />}
        {tab === "clubs" && <ClubsAdmin />}
        {tab === "users" && <UsersAdmin />}
      </div>
    </div>
  );
}
