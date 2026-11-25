"use client";
import { motion } from "motion/react";

/** Headline mask-reveal, word by word. Used once, on the hero. */
export function LineReveal({ text, delay = 0 }: { text: string; delay?: number }) {
  return (
    <span aria-label={text}>
      {text.split(" ").map((w, i) => (
        <span key={i} aria-hidden className="inline-block overflow-hidden align-bottom pb-[.08em] -mb-[.08em]" style={{ marginRight: ".22em" }}>
          <motion.span className="inline-block" initial={{ y: "108%" }} animate={{ y: 0 }} transition={{ duration: .9, ease: [.2, .8, .2, 1], delay: delay + i * .055 }}>{w}</motion.span>
        </span>
      ))}
    </span>
  );
}
