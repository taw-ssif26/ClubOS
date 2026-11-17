"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Spinner, StarInput, Stars, Textarea } from "./ui";

export function Reviews({ kind, slug, canReply = false }: { kind: "clubs" | "events"; slug: string; canReply?: boolean }) {
  const { user } = useAuth();
  const toast = useToast();
  const [data, setData] = useState<any>(null);
  const [form, setForm] = useState({ rating: 0, title: "", body: "" });
  const [replying, setReplying] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api(`/${kind}/${slug}/reviews`).then((d) => { setData(d); if (d.mine) setForm({ rating: d.mine.rating, title: d.mine.title, body: d.mine.body }); }).catch(() => setData({ summary: { count: 0, average: null, histogram: {} }, items: [], reason: "" })), [kind, slug]);
  useEffect(() => { load(); }, [load, user?.id]);

  const run = async (fn: () => Promise<any>, ok: string) => { setBusy(true); try { await fn(); toast(ok); await load(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  if (!data) return <Spinner />;
  const s = data.summary, max = Math.max(1, ...Object.values<number>(s.histogram || {}));
  return (
    <section aria-labelledby="reviews-h">
      <h2 id="reviews-h" className="display h-lg">Ratings and reviews</h2>
      <div className="mt-8 grid grid-cols-1 gap-10 md:grid-cols-[240px_1fr]">
        <div>
          <p className="display" style={{ fontSize: "5rem", lineHeight: 1 }}>{s.average ?? "–"}</p>
          <Stars value={s.average} size={20} />
          <p className="muted text-sm mt-2">{s.count ? `${s.count} review${s.count > 1 ? "s" : ""}` : "No reviews yet"}</p>
          <div className="mt-5 space-y-1.5" aria-hidden>
            {[5, 4, 3, 2, 1].map((n) => (
              <div key={n} className="flex items-center gap-2 text-xs"><span className="w-3">{n}</span>
                <div className="h-1.5 flex-1" style={{ background: "var(--bg3)" }}><div className="h-full transition-all duration-700" style={{ width: `${((s.histogram?.[n] || 0) / max) * 100}%`, background: "var(--accent)" }} /></div>
                <span className="w-5 muted text-right">{s.histogram?.[n] || 0}</span></div>))}
          </div>
        </div>
        <div className="space-y-8">
          {user && data.can_review && (
            <div className="panel p-6 space-y-4">
              <p className="font-semibold">{data.mine ? "Edit your review" : "Share your experience"}</p>
              <StarInput value={form.rating} onChange={(n) => setForm({ ...form, rating: n })} />
              <Field label="Headline (optional)"><Input maxLength={120} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
              <Textarea maxLength={2000} placeholder="What was it like?" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
              <div className="flex gap-3">
                <Button variant="primary" loading={busy} disabled={!form.rating} onClick={() => run(() => api(`/${kind}/${slug}/reviews/mine`, { method: "PUT", body: form }), "Review saved")}>{data.mine ? "Save changes" : "Publish review"}</Button>
                {data.mine && <Button variant="danger" onClick={() => run(async () => { await api(`/${kind}/${slug}/reviews/mine`, { method: "DELETE" }); setForm({ rating: 0, title: "", body: "" }); }, "Review deleted")}>Delete</Button>}
              </div>
            </div>
          )}
          {!data.can_review && data.reason && <p className="muted text-sm">{data.reason}.</p>}
          {data.items.length === 0 && <p className="muted">Be the first to review.</p>}
          {data.items.map((r: any) => (
            <article key={r.id} className="border-b border-line pb-6">
              <div className="flex items-center gap-3"><Stars value={r.rating} /><span className="muted text-sm">{fmtDate(r.created_at)}</span></div>
              {r.title && <h3 className="font-semibold mt-2">{r.title}</h3>}
              {r.body && <p className="mt-1 max-w-[65ch]">{r.body}</p>}
              <p className="muted text-sm mt-2">{r.user.full_name}</p>
              {r.reply && <div className="mt-3 pl-4 border-l-2" style={{ borderColor: "var(--accent)" }}><p className="text-sm font-semibold">Reply from the club</p><p className="muted text-sm">{r.reply}</p></div>}
              <div className="mt-2 flex gap-4 text-sm">
                {user && !r.mine && <button className="link muted" onClick={() => run(() => api(`/reviews/${r.id}/report`, { method: "POST" }), "Reported. A moderator will take a look.")}>Report</button>}
                {canReply && <button className="link muted" onClick={() => { setReplying(r.id); setReply(r.reply || ""); }}>{r.reply ? "Edit reply" : "Reply"}</button>}
              </div>
              {replying === r.id && (
                <div className="mt-3 space-y-2"><Textarea value={reply} onChange={(e) => setReply(e.target.value)} maxLength={1000} />
                  <div className="flex gap-2"><Button size="sm" variant="primary" disabled={!reply.trim()} onClick={() => run(async () => { await api(`/clubs/${slug}/reviews/${r.id}/reply`, { method: "PUT", body: { reply } }); setReplying(null); }, "Reply posted")}>Post reply</Button><Button size="sm" onClick={() => setReplying(null)}>Cancel</Button></div></div>)}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
