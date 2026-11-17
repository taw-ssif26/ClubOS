"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { bytes } from "@/lib/format";
import { uploadImage } from "@/lib/upload";
import { useToast } from "@/lib/toast";
import { FieldBuilder } from "../FieldBuilder";
import { Button, Field, Input, Select, Textarea, Upgrade } from "../ui";
import type { Ctx } from "./ManageClient";

const CATS = ["general", "technology", "science", "arts", "culture", "sports", "business", "debate", "social", "academic", "media"];
const FREE_PRESETS = ["minimal", "editorial", "academic"];

export function Settings({ slug, club, usage, reload }: Ctx) {
  const toast = useToast();
  const L = usage.limits;
  const [f, setF] = useState({ name: club.name, description: club.description, category: club.category, visibility: club.visibility, join_policy: club.join_policy, contact_email: club.contact_email || "", logo_url: club.logo_url || "", cover_url: club.cover_url || "" });
  const [t, setT] = useState({ preset: "minimal", primary: "#0d4a37", secondary: "", accent: "", font: "display-serif", hide_branding: false, ...(club.theme || {}) });
  const [app, setApp] = useState<any[]>(club.application_fields || []);
  const [files, setFiles] = useState<any>(null);
  const [upsell, setUpsell] = useState("");
  const loadFiles = () => api(`/clubs/${slug}/uploads`).then(setFiles).catch(() => {});
  useEffect(() => { loadFiles(); }, [slug]);

  const patch = async (body: any, ok: string) => {
    setUpsell("");
    try { await api(`/clubs/${slug}`, { method: "PATCH", body }); toast(ok); await reload(); }
    catch (e: any) { if (e instanceof ApiError && e.status === 402) setUpsell(e.message); else toast(e.message, "err"); }
  };
  const upload = (key: "logo_url" | "cover_url") => async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    try { const url = await uploadImage(slug, file); setF((s) => ({ ...s, [key]: url })); loadFiles(); toast("Uploaded. Save the profile to apply it."); } catch (x: any) { toast(x.message, "err"); }
  };
  const theme: any = { preset: t.preset, primary: t.primary, hide_branding: t.hide_branding };
  if (L.advanced_themes) { if (t.secondary) theme.secondary = t.secondary; if (t.accent) theme.accent = t.accent; theme.font = t.font; }

  return (
    <div className="space-y-16 max-w-4xl">
      <section className="space-y-6"><h2 className="display h-lg">Profile</h2>
        <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Description"><Textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <Field label="Category"><Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Contact email"><Input type="email" value={f.contact_email} onChange={(e) => setF({ ...f, contact_email: e.target.value })} /></Field>
          <Field label="Who can see the club"><Select value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value })}><option value="public">Everyone (listed)</option><option value="unlisted">Anyone with the link</option><option value="private">Members only</option>{club.institution && <option value="institution">Institution only</option>}</Select></Field>
          <Field label="How people join"><Select value={f.join_policy} onChange={(e) => setF({ ...f, join_policy: e.target.value })}><option value="open">Anyone can join</option><option value="request">Approval required</option><option value="invite">Invitation only</option></Select></Field></div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <Field label="Logo">{f.logo_url && <img src={f.logo_url} alt="" className="h-16 w-16 object-cover border border-line mb-2" />}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={upload("logo_url")} /></Field>
          <Field label="Cover image">{f.cover_url && <img src={f.cover_url} alt="" className="h-16 w-28 object-cover border border-line mb-2" />}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={upload("cover_url")} /></Field></div>
        <Button variant="primary" onClick={() => patch({ ...f, contact_email: f.contact_email || null, logo_url: f.logo_url || null, cover_url: f.cover_url || null }, "Profile saved")}>Save profile</Button></section>

      <section className="space-y-6"><h2 className="display h-lg">Look and feel</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <Field label="Theme"><Select value={t.preset} onChange={(e) => setT({ ...t, preset: e.target.value })}>{["minimal", "editorial", "academic", "modern", "bold", "professional"].map((p) => <option key={p} value={p} disabled={!L.advanced_themes && !FREE_PRESETS.includes(p)}>{p}{!L.advanced_themes && !FREE_PRESETS.includes(p) ? " (Pro)" : ""}</option>)}</Select></Field>
          <Field label="Brand color"><div className="flex gap-3 items-center"><input type="color" aria-label="Brand color" value={t.primary} onChange={(e) => setT({ ...t, primary: e.target.value })} /><Input value={t.primary} onChange={(e) => setT({ ...t, primary: e.target.value })} /></div></Field>
          <Field label="Secondary color (Pro)"><Input disabled={!L.advanced_themes} placeholder="#RRGGBB" value={t.secondary} onChange={(e) => setT({ ...t, secondary: e.target.value })} /></Field>
          <Field label="Typography (Pro)"><Select disabled={!L.advanced_themes} value={t.font} onChange={(e) => setT({ ...t, font: e.target.value })}><option value="display-serif">Display serif</option><option value="grotesk">Grotesk</option><option value="humanist">Humanist</option><option value="mono">Mono</option></Select></Field></div>
        <label className={`flex items-center gap-2 ${L.remove_branding ? "" : "opacity-60"}`}><input className="check" type="checkbox" disabled={!L.remove_branding} checked={!!t.hide_branding} onChange={(e) => setT({ ...t, hide_branding: e.target.checked })} />Hide the &quot;Run on ClubOS&quot; footer (Pro)</label>
        {upsell && <Upgrade message={upsell} />}
        <Button variant="primary" onClick={() => patch({ theme }, "Theme saved")}>Save theme</Button></section>

      <section className="space-y-6"><h2 className="display h-lg">Membership application</h2>
        <p className="muted max-w-2xl">Questions people answer when they ask to join. Leave empty to accept requests without questions.</p>
        <FieldBuilder fields={app} onChange={setApp} canConditions={!!L.conditional_logic} />
        <Button variant="primary" onClick={() => patch({ application_fields: app }, "Application form saved")}>Save application form</Button></section>

      <section className="space-y-4"><h2 className="display h-lg">Files</h2>
        {files && <><p className="muted">{bytes(files.used_bytes)} used{files.limit_bytes ? ` of ${bytes(files.limit_bytes)}` : ""}</p>
          <div className="grid grid-cols-1 gap-3 grid-cols-3 sm:grid-cols-5 lg:grid-cols-6">{files.items.map((i: any) => (
            <div key={i.id} className="relative group"><img src={i.url} alt={i.name} className="aspect-square object-cover border border-line w-full" />
              <button className="absolute inset-0 grid place-items-center text-sm opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: "color-mix(in oklab, var(--bg) 80%, transparent)" }}
                onClick={async () => { if (confirm("Delete this file? Anything using it will lose the image.")) { await api(`/clubs/${slug}/uploads/${i.id}`, { method: "DELETE" }); loadFiles(); } }}>Delete</button></div>))}</div></>}</section>
    </div>
  );
}
