"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Pic } from "./Pic";
import { Button } from "./ui";

export type Att = { id: string; url: string; name: string; size: number; kind: string; content_type?: string };
const EXT_ICON: Record<string, string> = { pdf: "PDF", docx: "DOC", xlsx: "XLS", pptx: "PPT", txt: "TXT", csv: "CSV" };
const ext = (n: string) => (n.split(".").pop() || "").toLowerCase();

/** Read-only display used on public pages: images as a gallery, documents as download chips. */
export function AttachmentList({ items }: { items?: Att[] | null }) {
  if (!items?.length) return null;
  const imgs = items.filter((a) => a.kind === "image"), docs = items.filter((a) => a.kind !== "image");
  return (
    <div className="mt-5 space-y-3">
      {imgs.length > 0 && <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{imgs.map((a) => (
        <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer" className="block overflow-hidden border border-line" style={{ borderRadius: "var(--r)" }}>
          <Pic src={a.url} alt={a.name} className="w-full h-36 object-cover transition-transform duration-500 hover:scale-105" fallback={<span className="muted text-xs p-3 block">{a.name}</span>} />
        </a>))}</div>}
      {docs.length > 0 && <ul className="space-y-2">{docs.map((a) => (
        <li key={a.id}><a href={a.url} download={a.name} className="flex items-center gap-3 border border-line px-3 py-2 hover:bg-[var(--bg3)] transition-colors" style={{ borderRadius: "var(--r)" }}>
          <span className="text-xs font-bold px-1.5 py-1" style={{ background: "var(--accent)", color: "var(--accent-fg)", borderRadius: 3 }}>{EXT_ICON[ext(a.name)] || "FILE"}</span>
          <span className="truncate flex-1">{a.name}</span><span className="muted text-xs shrink-0">{bytes(a.size)}</span></a></li>))}</ul>}
    </div>
  );
}

/** Editor: pick files, upload them to the club's storage, and choose which are attached to the post. */
export function AttachmentPicker({ slug, items, onChange }: { slug: string; items: Att[]; onChange: (a: Att[]) => void }) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const add = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    let list = [...items];
    for (const file of Array.from(files)) {
      if (list.length >= 10) { toast("A post can have up to 10 attachments", "err"); break; }
      try {
        const form = new FormData(); form.append("file", file);
        const r = await api(`/clubs/${slug}/uploads?only=any`, { method: "POST", form });
        list = [...list, { id: r.id, url: r.url, name: r.name, size: r.size, kind: r.kind }];
      } catch (e: any) { toast(`${file.name}: ${e.message}`, "err"); }
    }
    onChange(list); setBusy(false);
    if (input.current) input.current.value = "";
  };
  return (
    <div className="space-y-3">
      <p className="label">Attachments</p>
      {items.length > 0 && <ul className="space-y-2">{items.map((a) => (
        <li key={a.id} className="flex items-center gap-3 border border-line px-3 py-2 text-sm" style={{ borderRadius: "var(--r)" }}>
          {a.kind === "image" ? <Pic src={a.url} className="w-10 h-10 object-cover" /> : <span className="text-xs font-bold px-1.5 py-1" style={{ background: "var(--accent)", color: "var(--accent-fg)", borderRadius: 3 }}>{EXT_ICON[ext(a.name)] || "FILE"}</span>}
          <span className="truncate flex-1">{a.name}</span><span className="muted text-xs">{bytes(a.size)}</span>
          <Button size="sm" variant="danger" onClick={() => onChange(items.filter((x) => x.id !== a.id))} aria-label={`Remove ${a.name}`}>✕</Button></li>))}</ul>}
      <input ref={input} type="file" multiple hidden accept="image/png,image/jpeg,image/webp,.pdf,.docx,.xlsx,.pptx,.txt,.csv" onChange={(e) => add(e.target.files)} />
      <Button size="sm" loading={busy} onClick={() => input.current?.click()}>Attach images or documents</Button>
      <p className="muted text-xs">Images (PNG, JPEG, WebP) and PDF, Word, Excel, PowerPoint, TXT or CSV. Removing here only detaches the file from this post.</p>
    </div>
  );
}
