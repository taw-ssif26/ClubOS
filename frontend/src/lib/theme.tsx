"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Mode = "dark" | "light" | "fx";
const Ctx = createContext<{ mode: Mode; setMode: (m: Mode, origin?: { x: number; y: number }) => void }>({ mode: "dark", setMode: () => {} });
export const useTheme = () => useContext(Ctx);

/** Runs before first paint (inlined in <head>) so there is never a flash of the wrong mode. */
export const themeBootScript = `try{var m=localStorage.getItem("clubos-mode");if(m!=="dark"&&m!=="light"&&m!=="fx"){m=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.dataset.mode=m}catch(e){document.documentElement.dataset.mode="dark"}`;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<Mode>("dark");
  useEffect(() => setModeState((document.documentElement.dataset.mode as Mode) || "dark"), []);

  const setMode = useCallback((next: Mode, origin?: { x: number; y: number }) => {
    const apply = () => { document.documentElement.dataset.mode = next; localStorage.setItem("clubos-mode", next); setModeState(next); };
    const doc = document as any;
    if (!doc.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return apply();
    const x = origin?.x ?? innerWidth / 2, y = origin?.y ?? 0;
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    doc.startViewTransition(apply).ready.then(() =>
      document.documentElement.animate({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 750, easing: "cubic-bezier(.2,.7,.2,1)", pseudoElement: "::view-transition-new(root)" }));
  }, []);
  return <Ctx.Provider value={{ mode, setMode }}>{children}</Ctx.Provider>;
}
