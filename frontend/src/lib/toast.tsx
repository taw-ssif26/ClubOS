"use client";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useState } from "react";

type T = { id: number; text: string; kind: "ok" | "err" };
const Ctx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const push = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, kind }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === "err" ? 6000 : 3200);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 w-[min(380px,calc(100vw-2.5rem))]" role="status" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} layout initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }}
              className="panel px-4 py-3 text-sm" style={{ borderLeft: `3px solid ${t.kind === "ok" ? "var(--ok)" : "var(--danger)"}`, background: "var(--bg3)" }}>
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}
