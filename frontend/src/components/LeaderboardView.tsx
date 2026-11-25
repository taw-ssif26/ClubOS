"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Empty, Field, Input, Select, Spinner, Tabs } from "./ui";

/** Club-private leaderboard. Members see the ranking and their own history; people with points.manage can award and revoke. */
export function LeaderboardView({ slug }: { slug: string }) {
  const toast = useToast();
  const [period, setPeriod] = useState("all");
  const [data, setData] = useState<any>(null);
  const [off, setOff] = useState(false);
  const [mine, setMine] = useState<any[]>([]);
  const [recent, setRecent] = useState<any[]>([]);
  const [members, setMembers] = useState<any[] | null>(null);
  const [f, setF] = useState({ username: "", points: 10, reason: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api(`/clubs/${slug}/leaderboard?period=${period}`);
      setData(d);
      api(`/clubs/${slug}/leaderboard/history`).then(setMine).catch(() => {});
      if (d.can_award) api(`/clubs/${slug}/leaderboard/recent`).then(setRecent).catch(() => {});
    } catch (e: any) { if (e.code === "leaderboard_off" || e.status === 404) setOff(true); }
  }, [slug, period]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (data?.can_award && members === null) api(`/clubs/${slug}/members?status=active&limit=100`).then(setMembers).catch(() => setMembers([])); }, [data?.can_award, members, slug]);

  if (off) return <Empty title="No leaderboard" body="This club hasn't turned its leaderboard on." />;
  if (!data) return <Spinner />;
  const award = async () => {
    setBusy(true);
    try { await api(`/clubs/${slug}/leaderboard/awards`, { method: "POST", body: { username: f.username.trim(), points: Number(f.points), reason: f.reason } }); toast("Points recorded"); setF({ ...f, reason: "" }); load(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <div className="grid grid-cols-1 gap-14 lg:grid-cols-[1.2fr_1fr]">
      <section>
        <Tabs id="lb" value={period} onChange={setPeriod} tabs={[{ id: "all", label: "All time" }, { id: "month", label: "This month" }]} />
        {data.entries.length === 0 ? <Empty title="No points yet" body={data.can_award ? "Award the first points to start the board." : "Organizers award points for contributions."} /> : (
          <ol className="mt-6 divide-y divide-[var(--line)] border-y border-line">
            {data.entries.map((e: any) => (
              <li key={e.user.username} className="py-3.5 flex items-center gap-4" style={e.is_me ? { background: "var(--bg2)", boxShadow: "inset 3px 0 0 var(--accent)" } : undefined}>
                <span className="display w-10 text-center" style={{ fontSize: "1.8rem", lineHeight: 1, color: e.rank <= 3 ? "var(--accent)" : "var(--muted)" }}>{e.rank}</span>
                <span className="flex-1 min-w-0 truncate">{e.user.name}{e.is_me && <span className="muted text-sm"> (you)</span>}</span>
                <span className="display" style={{ fontSize: "1.5rem" }}>{e.points}</span>
              </li>))}
          </ol>)}
        <p className="muted text-sm mt-4">{data.me ? `You are ranked #${data.me.rank} with ${data.me.points} points.` : "You have no points in this period yet."} Visible only to members of this club.</p>
        {mine.length > 0 && (<div className="mt-10"><h3 className="display h-md mb-3">Your points</h3>
          <ul className="divide-y divide-[var(--line)] border-y border-line text-sm">{mine.map((h) => (
            <li key={h.id} className="py-2.5 flex gap-3"><span className="font-semibold w-14" style={{ color: h.points > 0 ? "var(--ok)" : "var(--danger)" }}>{h.points > 0 ? "+" : ""}{h.points}</span><span className="flex-1">{h.reason}</span><span className="muted shrink-0">{fmtDate(h.at)}</span></li>))}</ul></div>)}
      </section>

      {data.can_award && (
        <aside className="space-y-10">
          <section className="panel p-6 space-y-5 self-start">
            <h2 className="display h-md">Award points</h2>
            <Field label="Member">{members && members.length ? (
              <Select value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })}><option value="">Choose…</option>{members.map((m) => <option key={m.id} value={m.user.username}>{m.user.full_name} (@{m.user.username})</option>)}</Select>)
              : <Input placeholder="username" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} />}</Field>
            <Field label="Points" hint="Use a negative number to deduct (-500 to 500). You can't award yourself."><Input type="number" min={-500} max={500} value={f.points} onChange={(e) => setF({ ...f, points: Number(e.target.value) })} /></Field>
            <Field label="Contribution" hint="Everyone you award sees this reason."><Input maxLength={200} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
            <Button variant="primary" loading={busy} disabled={!f.username || !f.points || f.reason.trim().length < 3} onClick={award}>Record points</Button>
          </section>
          <section><h3 className="display h-md mb-3">Recent awards</h3>
            {recent.length === 0 ? <p className="muted text-sm">Nothing yet.</p> : (
              <ul className="divide-y divide-[var(--line)] border-y border-line text-sm">{recent.map((r) => (
                <li key={r.id} className="py-2.5 flex gap-3 items-start"><span className="font-semibold w-12 shrink-0" style={{ color: r.points > 0 ? "var(--ok)" : "var(--danger)" }}>{r.points > 0 ? "+" : ""}{r.points}</span>
                  <span className="flex-1"><strong>{r.to}</strong> · {r.reason}<span className="muted block text-xs">by {r.by}, {fmtDate(r.at)}</span></span>
                  <button className="link muted" onClick={async () => { if (confirm("Remove this entry?")) { await api(`/clubs/${slug}/leaderboard/awards/${r.id}`, { method: "DELETE" }); load(); } }}>Remove</button></li>))}</ul>)}</section>
        </aside>
      )}
    </div>
  );
}
