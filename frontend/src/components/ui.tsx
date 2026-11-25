"use client";
import Link from "next/link";
import { motion } from "motion/react";
import React, { useId, useState } from "react";

type BtnProps = { href?: string; variant?: "primary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>;
export function Button({ href, variant = "ghost", size = "md", loading, className = "", children, ...rest }: BtnProps) {
  const cls = `btn ${variant === "primary" ? "btn-primary" : variant === "danger" ? "btn-danger" : ""} ${size === "sm" ? "btn-sm" : ""} ${className}`;
  if (href) return <Link href={href} className={cls}>{children}</Link>;
  return <button className={cls} disabled={loading || rest.disabled} {...rest}>{loading ? "Working…" : children}</button>;
}

export function Field({ label, error, hint, children, className = "" }: { label?: string; error?: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="label">{label}</span>}
      {children}
      {hint && !error && <span className="muted text-xs mt-1 block">{hint}</span>}
      {error && <span className="err block">{error}</span>}
    </label>
  );
}
export const Input = (p: React.InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={`input ${p.className || ""}`} />;
export const Textarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={`textarea ${p.className || ""}`} />;
export const Select = (p: React.SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={`select ${p.className || ""}`} />;

export function Tabs({ tabs, value, onChange, id = "tabs" }: { tabs: { id: string; label: string; badge?: number | string }[]; value: string; onChange: (v: string) => void; id?: string }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line -mx-1 px-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className="relative px-4 py-3 text-sm whitespace-nowrap transition-colors" style={{ color: value === t.id ? "var(--fg)" : "var(--muted)" }}>
          {t.label}{t.badge ? <span className="ml-2 text-xs px-1.5 py-0.5" style={{ background: "var(--accent)", color: "var(--accent-fg)", borderRadius: 99 }}>{t.badge}</span> : null}
          {value === t.id && <motion.span layoutId={`${id}-u`} className="absolute left-0 right-0 -bottom-px h-[2px]" style={{ background: "var(--accent)" }} />}
        </button>
      ))}
    </div>
  );
}

const STAR = "M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3 6.1 20.6l1.3-6.6L2.5 9.4l6.6-.8z";
export function Stars({ value, size = 16 }: { value: number | null | undefined; size?: number }) {
  const uid = useId();
  const v = value || 0;
  return (
    <span className="inline-flex gap-[2px] align-middle" role="img" aria-label={value ? `${value} out of 5 stars` : "No ratings yet"}>
      {[0, 1, 2, 3, 4].map((i) => {
        const f = Math.max(0, Math.min(1, v - i));
        return (
          <svg key={i} width={size} height={size} viewBox="0 0 24 24" aria-hidden>
            <defs><linearGradient id={`${uid}${i}`}><stop offset={`${f * 100}%`} stopColor="var(--accent)" /><stop offset={`${f * 100}%`} stopColor="transparent" /></linearGradient></defs>
            <path d={STAR} fill={`url(#${uid}${i})`} stroke="var(--accent)" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
        );
      })}
    </span>
  );
}
export function StarInput({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  const show = hover || value;
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Rating" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <motion.button type="button" key={n} role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`} whileTap={{ scale: .8 }}
          onMouseEnter={() => setHover(n)} onFocus={() => setHover(n)} onBlur={() => setHover(0)} onClick={() => onChange(n)} className="p-0.5">
          <svg width="30" height="30" viewBox="0 0 24 24"><path d={STAR} fill={n <= show ? "var(--accent)" : "transparent"} stroke="var(--accent)" strokeWidth="1.2" strokeLinejoin="round" /></svg>
        </motion.button>
      ))}
    </div>
  );
}

export function Seal({ title = "Verified by ClubOS" }: { title?: string }) {
  return (
    <svg className="seal" viewBox="0 0 24 24" role="img" aria-label={title}><title>{title}</title>
      <path fill="currentColor" d="M12 1.5l2.3 1.7 2.8-.2 1 2.6 2.4 1.5-.6 2.8 1.2 2.5-1.8 2.2-.1 2.8-2.7.9-1.6 2.3-2.7-.9-2.7.9-1.6-2.3-2.7-.9-.1-2.8L2.4 12.4l1.2-2.5-.6-2.8 2.4-1.5 1-2.6 2.8.2z" />
      <path d="M8 12.2l2.9 2.9L16.2 9.6" fill="none" stroke="var(--bg)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export const Tag = ({ children, kind }: { children: React.ReactNode; kind?: "live" | "soon" }) => <span className={`tag ${kind ? `tag-${kind}` : ""}`}>{children}</span>;
export const Spinner = () => <div className="muted py-10 text-center caret">Loading</div>;
export function Empty({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return <div className="py-14 text-center"><p className="display h-md">{title}</p>{body && <p className="muted mt-2 max-w-md mx-auto">{body}</p>}{action && <div className="mt-5">{action}</div>}</div>;
}
export const Upgrade = ({ feature, message }: { feature?: string; message: string }) => (
  <div className="panel p-5 flex flex-wrap items-center gap-4 justify-between" style={{ borderColor: "var(--accent)" }}>
    <div><p className="font-semibold">{message}</p><p className="muted text-sm">Pro adds {feature || "more room and automation"}.</p></div>
    <Button href="/upgrade" variant="primary" size="sm">See plans</Button>
  </div>
);
