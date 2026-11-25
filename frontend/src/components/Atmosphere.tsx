"use client";
import { useEffect } from "react";

/** Fixed background layers per mode + the pointer tracking that drives spotlight and card sheen. */
export function Atmosphere() {
  useEffect(() => {
    const root = document.documentElement;
    let raf = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        root.style.setProperty("--px", `${e.clientX}px`);
        root.style.setProperty("--py", `${e.clientY}px`);
        const el = (e.target as HTMLElement | null)?.closest?.(".sheen") as HTMLElement | null;
        if (el) { const r = el.getBoundingClientRect(); el.style.setProperty("--sx", `${e.clientX - r.left}px`); el.style.setProperty("--sy", `${e.clientY - r.top}px`); }
      });
    };
    addEventListener("pointermove", move, { passive: true });
    return () => { removeEventListener("pointermove", move); cancelAnimationFrame(raf); };
  }, []);
  return (<><div className="atmos atmos-grid" aria-hidden /><div className="atmos atmos-spot" aria-hidden /><div className="atmos atmos-grain" aria-hidden style={{ zIndex: 3 }} /><div className="atmos atmos-fx" aria-hidden /></>);
}
