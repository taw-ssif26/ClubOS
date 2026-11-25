"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select, Spinner, Tag } from "../ui";
import { JsonForm } from "./JsonForm";

const TITLES: Record<string, string> = { "site.brand": "Brand and contact", nav: "Navigation", "home.hero": "Home: hero", "home.proof": "Home: ticker", "home.problem": "Home: problem statement", "home.features": "Home: features", "home.how": "Home: how it works", "home.reviews": "Home: reviews heading", "home.cta": "Home: closing call to action", "pricing.page": "Pricing page and FAQ", "discover.page": "Discover page", footer: "Footer" };

export function ContentEditor() {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [key, setKey] = useState("home.hero");
  const [val, setVal] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api("/admin/content").then((r) => { setRows(r); setVal(r.find((x: any) => x.key === key)?.value); });
  useEffect(() => { load(); }, []);
  const pick = (k: string) => { setKey(k); setVal(rows?.find((x) => x.key === k)?.value); };
  const save = async () => { setBusy(true); try { await api(`/admin/content/${key}`, { method: "PUT", body: { value: val } }); toast("Published. Live within seconds."); load(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const reset = async () => { if (!confirm("Restore the original copy for this section?")) return; await api(`/admin/content/${key}/reset`, { method: "POST" }); toast("Restored"); load(); };
  if (!rows) return <Spinner />;
  return (
    <div className="grid grid-cols-1 gap-10 lg:grid-cols-[260px_1fr]">
      <ul className="space-y-1 self-start lg:sticky lg:top-24">{rows.map((r) => <li key={r.key}><button onClick={() => pick(r.key)} className="w-full text-left px-3 py-2 text-sm transition-colors" style={{ background: key === r.key ? "var(--bg3)" : "transparent", borderLeft: `2px solid ${key === r.key ? "var(--accent)" : "transparent"}` }}>{TITLES[r.key] || r.key}</button></li>)}</ul>
      <div className="panel p-7 space-y-6 min-w-0">
        <div className="flex justify-between gap-4 flex-wrap items-center"><h2 className="display h-md">{TITLES[key] || key}</h2><div className="flex gap-2"><Button size="sm" onClick={reset}>Restore original</Button><Button size="sm" variant="primary" loading={busy} onClick={save}>Publish changes</Button></div></div>
        {val && <JsonForm value={val} onChange={setVal} />}
      </div>
    </div>
  );
}

const FLAGS = ["bulk_email", "conditional_logic", "waitlist", "advanced_themes", "advanced_analytics", "remove_branding"];
const LIMITS: [string, string][] = [["members", "Members"], ["admins", "Admin seats"], ["active_events", "Active events"], ["storage_mb", "Storage (MB)"], ["emails_per_day", "Emails per day"]];

export function PlansEditor() {
  const toast = useToast();
  const [plans, setPlans] = useState<any[] | null>(null);
  const load = () => api("/admin/plans").then(setPlans);
  useEffect(() => { load(); }, []);
  const set = (key: string, patch: any) => setPlans((ps) => ps!.map((p) => (p.key === key ? { ...p, ...patch } : p)));
  const save = async (p: any) => { try { await api(`/admin/plans/${p.key}`, { method: "PUT", body: p }); toast(`${p.name} saved. Limits apply immediately.`); load(); } catch (e: any) { toast(e.message, "err"); } };
  if (!plans) return <Spinner />;
  return (
    <div className="space-y-10">
      <p className="muted max-w-3xl">Prices, limits and feature lists. Limits are enforced by the API the moment you save. Leave a limit empty for unlimited. Mark unreleased features &quot;Soon&quot; so the pricing page stays honest.</p>
      {plans.map((p) => (
        <section key={p.key} className="panel p-7 space-y-6">
          <div className="flex items-center gap-3"><h2 className="display h-md">{p.name}</h2><Tag>{p.key}</Tag></div>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <Field label="Name"><Input value={p.name} onChange={(e) => set(p.key, { name: e.target.value })} /></Field>
            <Field label="Price per month in ৳ (empty = custom)"><Input type="number" min={0} value={p.price_monthly ?? ""} onChange={(e) => set(p.key, { price_monthly: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
            <Field label="Price label shown"><Input value={p.price_label} onChange={(e) => set(p.key, { price_label: e.target.value })} /></Field>
            <Field label="Tagline" className="md:col-span-2"><Input value={p.tagline} onChange={(e) => set(p.key, { tagline: e.target.value })} /></Field>
            <Field label="Button label"><Input value={p.cta_label} onChange={(e) => set(p.key, { cta_label: e.target.value })} /></Field>
            <Field label="Sort order"><Input type="number" value={p.sort} onChange={(e) => set(p.key, { sort: Number(e.target.value) })} /></Field>
            <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={p.highlighted} onChange={(e) => set(p.key, { highlighted: e.target.checked })} />Highlight as recommended</label>
            <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={p.visible} onChange={(e) => set(p.key, { visible: e.target.checked })} />Visible on pricing page</label></div>
          <div><p className="font-semibold mb-3">Limits</p><div className="grid grid-cols-1 gap-5 sm:grid-cols-3 lg:grid-cols-5">{LIMITS.map(([k, l]) => <Field key={k} label={l}><Input type="number" min={0} placeholder="unlimited" value={p.limits[k] ?? ""} onChange={(e) => set(p.key, { limits: { ...p.limits, [k]: e.target.value === "" ? null : Number(e.target.value) } })} /></Field>)}</div></div>
          <div><p className="font-semibold mb-3">Features unlocked</p><div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">{FLAGS.map((k) => <label key={k} className="flex items-center gap-2 text-sm"><input className="check" type="checkbox" checked={!!p.limits[k]} onChange={(e) => set(p.key, { limits: { ...p.limits, [k]: e.target.checked } })} />{k.replace(/_/g, " ")}</label>)}</div></div>
          <div><p className="font-semibold mb-3">Feature list on the pricing page</p>
            <div className="space-y-2">{p.features.map((f: any, i: number) => (
              <div key={i} className="flex gap-2"><Input aria-label="Feature" value={f.label} onChange={(e) => set(p.key, { features: p.features.map((x: any, j: number) => (j === i ? { ...x, label: e.target.value } : x)) })} />
                <Select aria-label="Status" className="!w-28" value={f.status} onChange={(e) => set(p.key, { features: p.features.map((x: any, j: number) => (j === i ? { ...x, status: e.target.value } : x)) })}><option value="live">Live</option><option value="soon">Soon</option></Select>
                <Button size="sm" onClick={() => { const a = [...p.features]; if (i > 0) { [a[i - 1], a[i]] = [a[i], a[i - 1]]; set(p.key, { features: a }); } }}>↑</Button>
                <Button size="sm" variant="danger" onClick={() => set(p.key, { features: p.features.filter((_: any, j: number) => j !== i) })}>✕</Button></div>))}
              <Button size="sm" onClick={() => set(p.key, { features: [...p.features, { label: "", status: "live" }] })}>Add feature</Button></div></div>
          <Button variant="primary" onClick={() => save(p)}>Save {p.name}</Button>
        </section>))}
    </div>
  );
}

const blankOffer = { id: "", title: "", body: "", badge: "", cta_label: "", cta_url: "", plan_key: "", discount_percent: 0, placement: "banner", starts_at: "", ends_at: "", active: true };

export function OffersEditor() {
  const toast = useToast();
  const [rows, setRows] = useState<any[] | null>(null);
  const [f, setF] = useState<any>(null);
  const load = () => api("/admin/offers").then(setRows);
  useEffect(() => { load(); }, []);
  const save = async () => {
    const body = { ...f, plan_key: f.plan_key || null, starts_at: fromLocalInput(f.starts_at), ends_at: fromLocalInput(f.ends_at) };
    try { await api(f.id ? `/admin/offers/${f.id}` : "/admin/offers", { method: f.id ? "PUT" : "POST", body }); toast("Offer saved"); setF(null); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  if (!rows) return <Spinner />;
  return (
    <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_1.1fr]">
      <section><div className="flex justify-between items-center mb-5"><h2 className="display h-md">Offers</h2><Button size="sm" variant="primary" onClick={() => setF({ ...blankOffer })}>New offer</Button></div>
        {rows.length === 0 ? <p className="muted">No offers. Create one to show a banner across the site and discount a plan on the pricing page.</p> :
          <ul className="divide-y divide-[var(--line)] border-y border-line">{rows.map((o) => <li key={o.id} className="py-3 flex justify-between gap-4"><div><p className="font-semibold">{o.title}</p><p className="muted text-xs">{o.placement}{o.plan_key ? ` · ${o.plan_key} −${o.discount_percent}%` : ""}</p></div>
            <div className="flex gap-2 items-start"><Tag>{o.active ? "active" : "off"}</Tag><Button size="sm" onClick={() => setF({ ...o, plan_key: o.plan_key || "", starts_at: toLocalInput(o.starts_at), ends_at: toLocalInput(o.ends_at) })}>Edit</Button>
              <Button size="sm" variant="danger" onClick={async () => { if (confirm("Delete this offer?")) { await api(`/admin/offers/${o.id}`, { method: "DELETE" }); load(); } }}>✕</Button></div></li>)}</ul>}</section>
      {f && <section className="panel p-6 space-y-5 self-start">
        <Field label="Headline"><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Detail line"><Input value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Badge"><Input value={f.badge} onChange={(e) => setF({ ...f, badge: e.target.value })} /></Field>
          <Field label="Where it shows"><Select value={f.placement} onChange={(e) => setF({ ...f, placement: e.target.value })}><option value="banner">Site banner</option><option value="pricing">Pricing page</option><option value="both">Both</option></Select></Field>
          <Field label="Button label"><Input value={f.cta_label} onChange={(e) => setF({ ...f, cta_label: e.target.value })} /></Field>
          <Field label="Button link"><Input value={f.cta_url} placeholder="/pricing" onChange={(e) => setF({ ...f, cta_url: e.target.value })} /></Field>
          <Field label="Discounts plan"><Select value={f.plan_key} onChange={(e) => setF({ ...f, plan_key: e.target.value })}><option value="">None (announcement only)</option><option value="pro">Pro</option><option value="organization">Organization</option></Select></Field>
          <Field label="Discount %"><Input type="number" min={0} max={100} value={f.discount_percent} onChange={(e) => setF({ ...f, discount_percent: Number(e.target.value) })} /></Field>
          <Field label="Starts (optional)"><Input type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
          <Field label="Ends (optional)"><Input type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} /></Field></div>
        <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} />Active</label>
        <p className="muted text-xs">A pricing discount is shown to visitors. The price is confirmed when you approve the upgrade, so charge the discounted amount.</p>
        <div className="flex gap-3"><Button variant="primary" disabled={!f.title} onClick={save}>Save offer</Button><Button onClick={() => setF(null)}>Cancel</Button></div></section>}
    </div>
  );
}
