"use client";
import { motion } from "motion/react";
import { useTheme, type Mode } from "@/lib/theme";

const MODES: { id: Mode; label: string; icon: React.ReactNode }[] = [
  { id: "dark", label: "Dark", icon: <path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" fill="currentColor" /> },
  { id: "light", label: "Light", icon: <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" fill="none"><circle cx="12" cy="12" r="4" fill="currentColor" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" /></g> },
  { id: "fx", label: "Effects", icon: <path d="M4 7l5 5-5 5M12 18h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square" /> },
];

export function ModeSwitch() {
  const { mode, setMode } = useTheme();
  return (
    <div role="radiogroup" aria-label="Appearance" className="relative inline-flex border border-line p-[3px] gap-[2px]" style={{ borderRadius: "var(--r)" }}>
      {MODES.map((m) => (
        <button key={m.id} role="radio" aria-checked={mode === m.id} aria-label={`${m.label} mode`} title={`${m.label} mode`}
          onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMode(m.id, { x: r.left + r.width / 2, y: r.top + r.height / 2 }); }}
          className="relative w-8 h-7 grid place-items-center transition-colors" style={{ color: mode === m.id ? "var(--accent-fg)" : "var(--muted)", borderRadius: "var(--r)" }}>
          {mode === m.id && <motion.span layoutId="mode-pill" className="absolute inset-0" style={{ background: "var(--accent)", borderRadius: "var(--r)" }} transition={{ type: "spring", stiffness: 500, damping: 34 }} />}
          <svg className="relative" width="16" height="16" viewBox="0 0 24 24" aria-hidden>{m.icon}</svg>
        </button>
      ))}
    </div>
  );
}
