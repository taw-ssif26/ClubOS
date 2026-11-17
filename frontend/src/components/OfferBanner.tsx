"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { safeHref } from "@/lib/safe";

export function OfferBanner({ offers }: { offers: any[] }) {
  const [hidden, setHidden] = useState<string | null>("pending");
  const o = offers?.[0];
  useEffect(() => { setHidden(o && localStorage.getItem(`offer-${o.id}`) ? "yes" : null); }, [o]);
  if (!o || hidden) return null;
  return (
    <div className="above border-b border-line text-sm" style={{ background: "var(--accent)", color: "var(--accent-fg)" }}>
      <div className="wrap py-2 flex items-center gap-3 flex-wrap">
        {o.badge && <span className="font-bold px-2 py-0.5" style={{ background: "var(--accent-fg)", color: "var(--accent)", borderRadius: "var(--r)" }}>{o.badge}</span>}
        <span className="font-semibold">{o.title}</span>
        {o.body && <span className="opacity-80 hidden sm:inline">{o.body}</span>}
        {o.cta_url && <Link href={safeHref(o.cta_url)} className="underline underline-offset-4 font-semibold">{o.cta_label || "Learn more"}</Link>}
        <button className="ml-auto opacity-70 hover:opacity-100" aria-label="Dismiss offer" onClick={() => { localStorage.setItem(`offer-${o.id}`, "1"); setHidden("yes"); }}>✕</button>
      </div>
    </div>
  );
}
