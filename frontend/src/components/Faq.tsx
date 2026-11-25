"use client";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

export function Faq({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="border-t border-line">
      {items.map((it, i) => (
        <div key={i} className="border-b border-line">
          <button className="w-full flex justify-between gap-6 py-5 text-left" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
            <span className="display h-md" style={{ fontSize: "1.35rem" }}>{it.q}</span>
            <motion.span animate={{ rotate: open === i ? 45 : 0 }} className="text-2xl leading-none" style={{ color: "var(--accent)" }} aria-hidden>+</motion.span>
          </button>
          <AnimatePresence initial={false}>
            {open === i && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><p className="muted pb-6 max-w-[60ch]">{it.a}</p></motion.div>}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}
