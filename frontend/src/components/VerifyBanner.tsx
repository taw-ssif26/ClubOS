"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";

/** Shown to signed-in people whose email isn't verified yet: without it they can't create clubs or register for events. */
export function VerifyBanner() {
  const { user } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!user || user.email_verified) return null;
  const resend = async () => { setBusy(true); try { await api("/auth/resend-verification", { method: "POST" }); toast("Verification email sent. Check your inbox and spam folder."); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  return (
    <div className="above border-b border-line text-sm" style={{ background: "var(--bg3)" }}>
      <div className="wrap py-2.5 flex items-center gap-4 flex-wrap"><span>Verify your email to create clubs and register for events. We sent a link to <strong>{user.email}</strong>.</span>
        <button className="link" disabled={busy} onClick={resend}>{busy ? "Sending…" : "Resend email"}</button></div>
    </div>
  );
}
