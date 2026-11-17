"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { Button, Field, Input } from "./ui";

export function SecurityPanel() {
  const { user, refresh, logout } = useAuth();
  const toast = useToast();
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [setup, setSetup] = useState<{ secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [dis, setDis] = useState({ password: "", code: "" });
  const [del, setDel] = useState({ password: "", code: "", confirm: "" });
  if (!user) return null;
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok); return true; } catch (e: any) { toast(e.message, "err"); return false; } };

  return (
    <div className="grid grid-cols-1 gap-14 lg:grid-cols-2 mt-14 border-t border-line pt-14">
      <section className="space-y-5 max-w-md"><h2 className="display h-md">Change password</h2>
        <Field label="Current password"><Input type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
        <Field label="New password" hint="At least 10 characters. Other devices are signed out."><Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <Button variant="primary" disabled={pw.new_password.length < 10 || !pw.current_password} onClick={async () => { if (await run(() => api("/auth/change-password", { method: "POST", body: pw }), "Password changed")) setPw({ current_password: "", new_password: "" }); }}>Change password</Button></section>

      <section className="space-y-5 max-w-md"><h2 className="display h-md">Two-factor authentication</h2>
        {user.totp_enabled ? (<>
          <p className="muted">On. Signing in needs a code from your authenticator app.</p>
          <Field label="Password"><Input type="password" value={dis.password} onChange={(e) => setDis({ ...dis, password: e.target.value })} /></Field>
          <Field label="Current code"><Input inputMode="numeric" maxLength={6} value={dis.code} onChange={(e) => setDis({ ...dis, code: e.target.value })} /></Field>
          <Button variant="danger" onClick={async () => { if (await run(() => api("/auth/2fa/disable", { method: "POST", body: dis }), "Two-factor turned off")) { setDis({ password: "", code: "" }); refresh(); } }}>Turn off</Button></>)
        : !setup ? (<><p className="muted">Protect your account with a code from an authenticator app (Google Authenticator, Authy, 1Password). Required for platform admins.</p>
          <Button variant="primary" onClick={async () => { try { setSetup(await api("/auth/2fa/setup", { method: "POST" })); } catch (e: any) { toast(e.message, "err"); } }}>Set up</Button></>)
        : (<><p className="muted">Scan this with your authenticator app, then enter the 6-digit code it shows.</p>
          <img src={`/api/auth/2fa/qr.svg?${setup.secret.slice(0, 4)}`} alt="Two-factor setup QR code" width={190} height={190} style={{ background: "#fff", padding: 6 }} />
          <p className="text-sm muted">Can&apos;t scan? Enter this key: <code className="select-all" style={{ color: "var(--fg)" }}>{setup.secret}</code></p>
          <Field label="6-digit code"><Input inputMode="numeric" maxLength={6} autoFocus value={code} onChange={(e) => setCode(e.target.value)} /></Field>
          <Button variant="primary" disabled={code.length !== 6} onClick={async () => { if (await run(() => api("/auth/2fa/enable", { method: "POST", body: { code } }), "Two-factor is on")) { setSetup(null); setCode(""); refresh(); } }}>Turn on</Button></>)}
      </section>

      <section className="space-y-4 max-w-md"><h2 className="display h-md">Your data</h2>
        <p className="muted">Download everything ClubOS holds about you: profile, memberships, registrations, reviews and sign-in history.</p>
        <a className="btn" href="/api/users/me/export" download>Download my data</a></section>

      <section className="space-y-5 max-w-md"><h2 className="display h-md" style={{ color: "var(--danger)" }}>Delete account</h2>
        <p className="muted">Removes your name, email, profile, reviews and sessions. Clubs keep anonymous attendance totals. This cannot be undone. If you are a club&apos;s only Owner, promote someone else first.</p>
        <Field label="Password"><Input type="password" value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value })} /></Field>
        {user.totp_enabled && <Field label="Authentication code"><Input inputMode="numeric" maxLength={6} value={del.code} onChange={(e) => setDel({ ...del, code: e.target.value })} /></Field>}
        <Field label="Type DELETE to confirm"><Input value={del.confirm} onChange={(e) => setDel({ ...del, confirm: e.target.value })} /></Field>
        <Button variant="danger" disabled={del.confirm !== "DELETE" || !del.password} onClick={async () => { if (await run(() => api("/users/me", { method: "DELETE", body: { password: del.password, code: del.code || undefined } }), "Account deleted")) logout(); }}>Delete my account</Button></section>
    </div>
  );
}
