"use client";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { safeHref } from "@/lib/safe";
import { useAuth } from "@/lib/auth";
import { Logo } from "./Logo";
import { ModeSwitch } from "./ModeSwitch";

export function Nav({ brand, nav }: { brand: any; nav: any }) {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [unread, setUnread] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (user) api("/notifications?unread_only=true").then((n) => setUnread(n.length)).catch(() => {}); }, [user]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const links: { label: string; href: string }[] = nav?.links || [];
  return (
    <header className="sticky top-0 z-50 border-b border-line" style={{ background: "color-mix(in oklab, var(--bg) 86%, transparent)", backdropFilter: "blur(14px)" }}>
      <div className="wrap h-16 flex items-center gap-6">
        <Link href="/" aria-label={`${brand?.name || "ClubOS"} home`}><Logo name={brand?.name} /></Link>
        <nav className="hidden md:flex gap-6 ml-4 text-[.95rem]" aria-label="Primary">
          {links.map((l) => <Link key={l.href} href={safeHref(l.href)} className="link muted hover:text-[var(--fg)]">{l.label}</Link>)}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <ModeSwitch />
          {!loading && !user && (<>
            <Link href="/login" className="hidden sm:inline link text-[.95rem]">{nav?.login_label || "Sign in"}</Link>
            <Link href="/new-club" className="btn btn-primary btn-sm hidden sm:inline-flex">{nav?.cta_label || "Start a club"}</Link>
          </>)}
          {user && (
            <div className="relative" ref={menuRef}>
              <button onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu} className="flex items-center gap-2 border border-line px-2.5 py-1.5" style={{ borderRadius: "var(--r)" }}>
                <span className="grid place-items-center w-6 h-6 text-xs font-bold" style={{ background: "var(--accent)", color: "var(--accent-fg)", borderRadius: "50%" }}>{user.full_name[0]}</span>
                <span className="hidden sm:inline text-sm">{user.full_name.split(" ")[0]}</span>
                {unread > 0 && <span className="text-xs px-1.5" style={{ background: "var(--accent2)", color: "#fff", borderRadius: 99 }}>{unread}</span>}
              </button>
              <AnimatePresence>
                {menu && (
                  <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: .15 }}
                    className="panel absolute right-0 mt-2 w-56 py-2 text-sm" style={{ background: "var(--bg2)" }} onClick={() => setMenu(false)}>
                    <Link role="menuitem" className="block px-4 py-2 hover:bg-[var(--bg3)]" href="/me">My space</Link>
                    <Link role="menuitem" className="block px-4 py-2 hover:bg-[var(--bg3)]" href="/me?tab=notifications">Notifications{unread ? ` (${unread})` : ""}</Link>
                    <Link role="menuitem" className="block px-4 py-2 hover:bg-[var(--bg3)]" href="/new-club">Start a club</Link>
                    {user.is_platform_admin && <Link role="menuitem" className="block px-4 py-2 hover:bg-[var(--bg3)]" href="/admin">Super admin</Link>}
                    <hr className="rule my-1" />
                    <button role="menuitem" className="block w-full text-left px-4 py-2 hover:bg-[var(--bg3)]" onClick={logout}>Sign out</button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
          <button className="md:hidden p-2" aria-label="Menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            <svg width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d={open ? "M5 5l14 14M19 5L5 19" : "M4 8h16M4 16h16"} /></svg>
          </button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="md:hidden overflow-hidden border-t border-line" onClick={() => setOpen(false)}>
            <div className="wrap py-4 flex flex-col gap-3 text-lg">
              {links.map((l) => <Link key={l.href} href={safeHref(l.href)}>{l.label}</Link>)}
              {!user && <Link href="/login">{nav?.login_label || "Sign in"}</Link>}
              {!user && <Link href="/new-club" className="btn btn-primary">{nav?.cta_label || "Start a club"}</Link>}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
