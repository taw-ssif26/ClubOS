"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Field, Input } from "./ui";

type Kind = "login" | "register" | "forgot" | "reset" | "verify";
const COPY: Record<Kind, { title: string; sub: string }> = {
  login: { title: "Welcome back.", sub: "Sign in to your clubs, tickets and notifications." },
  register: { title: "One account for every club.", sub: "Join clubs, collect tickets, and keep your history in one place." },
  forgot: { title: "Reset your password.", sub: "Enter your email and we'll send a link that works for one hour." },
  reset: { title: "Choose a new password.", sub: "Signing in on other devices will end when you save." },
  verify: { title: "Confirming your email.", sub: "One moment." },
};
const safeNext = (n: string | null) => (n && n.startsWith("/") && !n.startsWith("//") ? n : "/me");

export function AuthForm({ kind }: { kind: Kind }) {
  const router = useRouter();
  const sp = useSearchParams();
  const { refresh } = useAuth();
  const [f, setF] = useState({ email: "", password: "", full_name: "", username: "", code: "" });
  const [accept, setAccept] = useState(false);
  const [needCode, setNeedCode] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);
  const token = sp.get("token") || "";
  const next = safeNext(sp.get("next"));
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    if (kind !== "verify") return;
    api("/auth/verify-email", { method: "POST", body: { token } }).then(() => { setDone("Your email is verified. You can now create clubs and register for events."); refresh(); }).catch((e) => setErr(e.message));
  }, [kind, token, refresh]);

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault(); setBusy(true); setErr("");
    try {
      if (kind === "login") { await api("/auth/login", { method: "POST", body: { email: f.email, password: f.password, code: f.code || undefined } }); await refresh(); router.push(next); }
      if (kind === "register") {
        await api("/auth/register", { method: "POST", body: { email: f.email, password: f.password, full_name: f.full_name, username: f.username.toLowerCase(), accept_terms: accept } });
        await api("/auth/login", { method: "POST", body: { email: f.email, password: f.password } }); await refresh();
        setDone("Account created. We sent a verification link to your email. Verify it to create clubs and register for events.");
      }
      if (kind === "forgot") { await api("/auth/password-reset/request", { method: "POST", body: { email: f.email } }); setDone("If that email has an account, a reset link is on its way."); }
      if (kind === "reset") { await api("/auth/password-reset/confirm", { method: "POST", body: { token, password: f.password } }); setDone("Password changed. You can sign in now."); }
    } catch (e: any) { if (e instanceof ApiError && e.code === "totp_required") { setNeedCode(true); setErr(""); } else setErr(e.message); } finally { setBusy(false); }
  };

  const c = COPY[kind];
  return (
    <div className="wrap py-20 grid grid-cols-1 gap-14 lg:grid-cols-[1.1fr_.9fr] items-start min-h-[70vh]">
      <div><h1 className="display h-xl">{c.title}</h1><p className="lede mt-6">{c.sub}</p></div>
      <div className="panel p-8">
        {done ? (<div><p className="display h-md">{done}</p><div className="mt-6 flex gap-3">{kind === "register" ? <Button href="/discover" variant="primary">Find clubs</Button> : <Button href="/login" variant="primary">Sign in</Button>}</div></div>)
        : kind === "verify" ? <p className={err ? "err" : "muted caret"}>{err || "Verifying"}</p>
        : (
          <form onSubmit={submit} className="space-y-6">
            {kind === "register" && <><Field label="Full name"><Input required value={f.full_name} onChange={set("full_name")} autoComplete="name" /></Field>
              <Field label="Username" hint="Lowercase letters, numbers and underscores"><Input required pattern="[a-zA-Z0-9_]{3,30}" value={f.username} onChange={set("username")} autoComplete="username" /></Field></>}
            {kind !== "reset" && <Field label="Email"><Input type="email" required value={f.email} onChange={set("email")} autoComplete="email" /></Field>}
            {kind !== "forgot" && <Field label={kind === "reset" ? "New password" : "Password"} hint={kind !== "login" ? "At least 10 characters" : undefined}><Input type="password" required minLength={kind === "login" ? 1 : 10} value={f.password} onChange={set("password")} autoComplete={kind === "login" ? "current-password" : "new-password"} /></Field>}
            {kind === "login" && needCode && <Field label="Authentication code" hint="From your authenticator app"><Input autoFocus inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required value={f.code} onChange={set("code")} autoComplete="one-time-code" /></Field>}
            {kind === "register" && <label className="flex items-start gap-2 text-sm"><input className="check mt-1" type="checkbox" required checked={accept} onChange={(e) => setAccept(e.target.checked)} /><span>I agree to the <Link className="link" href="/terms" target="_blank">Terms of Service</Link> and <Link className="link" href="/privacy" target="_blank">Privacy Policy</Link>.</span></label>}
            {err && <p className="err" role="alert">{err}</p>}
            <Button type="submit" variant="primary" className="w-full" loading={busy}>{{ login: "Sign in", register: "Create account", forgot: "Send reset link", reset: "Save password", verify: "" }[kind]}</Button>
            <div className="text-sm muted flex justify-between flex-wrap gap-2">
              {kind === "login" && <><Link className="link" href={`/register${sp.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}>Create an account</Link><Link className="link" href="/forgot-password">Forgot password?</Link></>}
              {kind === "register" && <Link className="link" href="/login">Already have an account?</Link>}
              {kind === "forgot" && <Link className="link" href="/login">Back to sign in</Link>}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
