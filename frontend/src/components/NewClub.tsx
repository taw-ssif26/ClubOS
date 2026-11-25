"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { slugify } from "@/lib/format";
import { LocationPicker, locPayload, type LocValue } from "./LocationPicker";
import { Button, Field, Input, Select, Textarea } from "./ui";

const CATS = ["general", "technology", "science", "arts", "culture", "sports", "business", "debate", "social", "academic", "media"];

export function NewClub() {
  const { user } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ name: "", slug: "", description: "", category: "general", visibility: "public", join_policy: "request", institution_slug: "" });
  const [loc, setLoc] = useState<LocValue>({ location_mode: "onsite", place: "", address: "", latitude: null, longitude: null });
  const [touched, setTouched] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<any>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const c = await api("/clubs", { method: "POST", body: { ...f, institution_slug: f.institution_slug || null, ...locPayload(loc) } });
      if (c.status === "pending") setSent(c); else router.push(`/manage/${c.slug}`);
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (sent) return (
    <div className="wrap py-24 max-w-2xl">
      <h1 className="display h-xl">Request received.</h1>
      <p className="lede mt-6">A ClubOS reviewer will look at <strong>{sent.name}</strong> and you&apos;ll get a notification and an email with the decision. Until then the club is visible only to you.</p>
      <p className="muted mt-4">You can already set it up: logo, location, events and posts. Inviting people, email and plan requests unlock after approval.</p>
      <div className="mt-9 flex gap-3"><Button href={`/manage/${sent.slug}`} variant="primary">Set up my club</Button><Button href="/me">My space</Button></div>
    </div>
  );
  return (
    <div className="wrap py-20 grid grid-cols-1 gap-14 lg:grid-cols-[.9fr_1.1fr]">
      <div><h1 className="display h-xl">Start your club.</h1>
        <p className="lede mt-6">Takes a minute. Every new club is checked by a ClubOS reviewer before it goes public, which keeps the directory free of spam. The free plan covers up to 100 members.</p>
        {user && !user.email_verified && <p className="mt-8 panel p-4 text-sm" style={{ borderColor: "var(--danger)" }}>Verify your email first. We sent you a link when you signed up.</p>}
        <p className="muted text-sm mt-8">You can have up to 2 clubs waiting for approval at once. Already approved? <Link className="link" href="/me">Go to your clubs</Link>.</p></div>
      <form onSubmit={submit} className="panel p-8 space-y-6">
        <Field label="Club name"><Input required minLength={2} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value, slug: touched ? f.slug : slugify(e.target.value) })} /></Field>
        <Field label="Web address" hint={`clubos.app/c/${f.slug || "your-club"}`}><Input required pattern="[a-z0-9][a-z0-9\-]{2,39}" value={f.slug} onChange={(e) => { setTouched(true); setF({ ...f, slug: e.target.value.toLowerCase() }); }} /></Field>
        <Field label="What is it about?" hint="At least 20 characters. Reviewers read this to confirm the club is real."><Textarea required minLength={20} maxLength={3000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Field label="Category"><Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Who can see it"><Select value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value })}><option value="public">Everyone</option><option value="unlisted">Link only</option><option value="private">Members only</option></Select></Field>
          <Field label="How people join"><Select value={f.join_policy} onChange={(e) => setF({ ...f, join_policy: e.target.value })}><option value="open">Anyone can join</option><option value="request">Approval required</option><option value="invite">Invitation only</option></Select></Field>
        </div>
        <div className="border-t border-line pt-6"><p className="font-semibold mb-4">Where does it meet?</p><LocationPicker value={loc} onChange={setLoc} /></div>
        {err && <p className="err" role="alert">{err}</p>}
        <Button type="submit" variant="primary" loading={busy}>Submit for review</Button>
      </form>
    </div>
  );
}
