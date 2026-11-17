"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Field, Input, Select, Spinner, Textarea } from "./ui";

export function UpgradeClient() {
  const sp = useSearchParams();
  const [clubs, setClubs] = useState<any[] | null>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [note, setNote] = useState("");
  const [f, setF] = useState({ club: "", plan_key: sp.get("plan") || "pro", months: 1, contact: "", message: "" });
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api("/users/me/memberships"), api("/pricing"), api("/content")]).then(([m, p, c]) => {
      const mine = m.filter((x: any) => x.status === "active" && (x.role === "Owner" || x.role === "Administrator"));
      setClubs(mine); setPlans(p.plans.filter((x: any) => x.key !== "free")); setNote(c["pricing.page"]?.billing_note || "");
      setF((s) => ({ ...s, club: mine[0]?.club.slug || "" }));
    }).catch(() => setClubs([]));
  }, []);
  const plan = plans.find((p) => p.key === f.plan_key);
  const unit = plan?.discounted_price ?? plan?.price_monthly;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await api(`/clubs/${f.club}/upgrade-requests`, { method: "POST", body: { plan_key: f.plan_key, months: f.months, contact: f.contact, message: f.message } }); setDone(true); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (!clubs) return <div className="wrap py-20"><Spinner /></div>;
  return (
    <div className="wrap py-20 grid grid-cols-1 gap-14 lg:grid-cols-[.9fr_1.1fr]">
      <div><h1 className="display h-xl">Upgrade your club.</h1><p className="lede mt-6">{note}</p></div>
      {done ? <div className="panel p-8"><p className="display h-md">Request received.</p><p className="muted mt-3">We&apos;ll contact you on {f.contact} to confirm payment. Your plan switches on as soon as it&apos;s confirmed, and you&apos;ll get a notification here.</p><div className="mt-6"><Button href={`/manage/${f.club}`}>Back to dashboard</Button></div></div>
      : clubs.length === 0 ? <div className="panel p-8"><p className="display h-md">You need a club to upgrade.</p><p className="muted mt-2">Only a club&apos;s owners and administrators can request a plan.</p><div className="mt-6"><Button href="/new-club" variant="primary">Start a club</Button></div></div>
      : (
        <form onSubmit={submit} className="panel p-8 space-y-6">
          <Field label="Club"><Select value={f.club} onChange={(e) => setF({ ...f, club: e.target.value })}>{clubs.map((c) => <option key={c.club.slug} value={c.club.slug}>{c.club.name}</option>)}</Select></Field>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Field label="Plan"><Select value={f.plan_key} onChange={(e) => setF({ ...f, plan_key: e.target.value })}>{plans.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}</Select></Field>
            <Field label="Months"><Select value={f.months} onChange={(e) => setF({ ...f, months: Number(e.target.value) })}>{[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m}</option>)}</Select></Field></div>
          {unit != null && <p className="display h-md">৳{(unit * f.months).toLocaleString("en-IN")} <span className="muted text-base" style={{ fontFamily: "var(--font-body)" }}>for {f.months} month{f.months > 1 ? "s" : ""}</span></p>}
          <Field label="bKash, Nagad or phone number we can confirm payment with"><Input required minLength={5} value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} /></Field>
          <Field label="Anything we should know? (optional)"><Textarea maxLength={1000} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} /></Field>
          {err && <p className="err" role="alert">{err}</p>}
          <Button type="submit" variant="primary" loading={busy}>Request upgrade</Button>
        </form>)}
    </div>
  );
}
