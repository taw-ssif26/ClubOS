"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDate, fromLocalInput, toLocalInput } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select, Spinner, Tag, Textarea } from "../ui";
import type { Ctx } from "./ManageClient";

const blank = { id: "", title: "", body: "", kind: "announcement", status: "draft", pinned: false, publish_at: "" };

export function Posts({ slug }: Ctx) {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [f, setF] = useState<any>(null);
  const load = () => api(`/clubs/${slug}/posts?drafts=true&limit=50`).then(setRows);
  useEffect(() => { load(); }, [slug]);
  const save = async () => {
    const body = { title: f.title, body: f.body, kind: f.kind, status: f.status, pinned: f.pinned, publish_at: fromLocalInput(f.publish_at) };
    try { await api(`/clubs/${slug}/posts${f.id ? `/${f.id}` : ""}`, { method: f.id ? "PATCH" : "POST", body }); toast("Post saved"); setF(null); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1fr_1.1fr]">
      <section>
        <div className="flex justify-between items-center mb-6"><h2 className="display h-md">Posts</h2><Button size="sm" variant="primary" onClick={() => setF({ ...blank })}>New post</Button></div>
        {!rows ? <Spinner /> : rows.length === 0 ? <p className="muted">Nothing posted yet.</p> : <ul className="divide-y divide-[var(--line)] border-y border-line">{rows.map((p) => (
          <li key={p.id} className="py-3 flex justify-between gap-4"><div><p className="font-semibold">{p.pinned && "📌 "}{p.title}</p><p className="muted text-xs">{p.kind} · {fmtDate(p.created_at)}</p></div>
            <div className="flex gap-2 items-start"><Tag>{p.status === "published" && p.publish_at && new Date(p.publish_at) > new Date() ? "scheduled" : p.status}</Tag>
              <Button size="sm" onClick={() => setF({ ...p, publish_at: toLocalInput(p.publish_at) })}>Edit</Button>
              <Button size="sm" variant="danger" onClick={async () => { if (confirm("Delete this post?")) { await api(`/clubs/${slug}/posts/${p.id}`, { method: "DELETE" }); load(); } }}>✕</Button></div></li>))}</ul>}
      </section>
      {f && (
        <section className="panel p-6 space-y-5 self-start">
          <Field label="Title"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Body"><Textarea style={{ minHeight: "11rem" }} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <Field label="Type"><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{["announcement", "news", "update", "achievement", "recruitment", "article", "notice"].map((k) => <option key={k}>{k}</option>)}</Select></Field>
            <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="draft">Draft</option><option value="published">Published</option></Select></Field>
            <Field label="Publish at (optional)" hint="Leave empty to publish immediately"><Input type="datetime-local" value={f.publish_at} onChange={(e) => setF({ ...f, publish_at: e.target.value })} /></Field>
            <label className="flex items-center gap-2 self-end pb-2"><input className="check" type="checkbox" checked={f.pinned} onChange={(e) => setF({ ...f, pinned: e.target.checked })} />Pin to top</label></div>
          <div className="flex gap-3"><Button variant="primary" disabled={!f.title || !f.body} onClick={save}>Save post</Button><Button onClick={() => setF(null)}>Cancel</Button></div>
        </section>)}
    </div>
  );
}
