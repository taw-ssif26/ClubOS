"use client";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

/** Decorative QR-like pattern derived from the serial (not a scannable code). */
function pattern(seed: string, n = 25) {
  let h = 2166136261;
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  const rnd = () => ((h = Math.imul(h ^ (h >>> 15), 2246822519)), ((h ^ (h >>> 13)) >>> 0) / 4294967296);
  const cells: [number, number][] = [];
  const finder = (x: number, y: number) => x < 8 && y < 8 || x > n - 9 && y < 8 || x < 8 && y > n - 9;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (!finder(x, y) && rnd() > 0.52) cells.push([x, y]);
  return cells;
}

export function HeroTicket({ t }: { t: { event: string; club: string; holder: string; serial: string } }) {
  const [phase, setPhase] = useState<"idle" | "scan" | "done">("idle");
  const [run, setRun] = useState(0);
  const cells = useMemo(() => pattern(t.serial), [t.serial]);

  useEffect(() => {
    setPhase("idle");
    const a = setTimeout(() => setPhase("scan"), 1200), b = setTimeout(() => setPhase("done"), 2500);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [run]);

  const corner = (x: number, y: number) => (
    <g key={`${x}${y}`} transform={`translate(${x} ${y})`}><rect width="7" height="7" fill="currentColor" /><rect x="1" y="1" width="5" height="5" fill="var(--bg2)" /><rect x="2" y="2" width="3" height="3" fill="currentColor" /></g>
  );
  return (
    <div className="relative mx-auto" style={{ width: "min(340px, 86vw)" }}>
      <motion.div initial={{ y: 70, rotate: 7, opacity: 0 }} animate={{ y: 0, rotate: -3, opacity: 1 }} transition={{ type: "spring", stiffness: 70, damping: 14, delay: .35 }}>
        <div className="ticket" style={{ ["--cut" as any]: "64%", background: "var(--bg2)", boxShadow: "0 40px 80px -30px rgba(0,0,0,.55)" }}>
          <div className="p-6 pb-8" style={{ height: "64%", minHeight: 300 }}>
            <p className="muted text-sm">{t.club}</p>
            <h2 className="display h-lg mt-3" style={{ fontSize: "clamp(2rem,3.4vw,2.7rem)" }}>{t.event}</h2>
            <div className="mt-8 grid grid-cols-2 gap-4 text-sm">
              <div><p className="muted">Admit</p><p className="font-semibold">{t.holder}</p></div>
              <div><p className="muted">Ticket</p><p className="font-semibold">{t.serial}</p></div>
            </div>
          </div>
          <div className="perf" />
          <div className="relative stub px-6 pb-6 flex items-center gap-5" style={{ minHeight: 170 }}>
            <div className="relative shrink-0" style={{ width: 116, height: 116, color: "var(--fg)" }}>
              <svg viewBox="0 0 25 25" width="116" height="116" shapeRendering="crispEdges" aria-hidden>
                {corner(0, 0)}{corner(18, 0)}{corner(0, 18)}
                {cells.map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="currentColor" />)}
              </svg>
              <motion.div className="scanline" key={run} initial={{ top: 0, opacity: 0 }}
                animate={phase === "scan" ? { top: ["0%", "100%", "0%"], opacity: [0, 1, 0] } : { opacity: 0 }} transition={{ duration: 1.3, ease: "easeInOut" }} />
            </div>
            <div className="text-sm min-w-0">
              <p className="muted">Gate</p>
              <p className="font-semibold" aria-live="polite">{phase === "idle" ? "Awaiting scan" : phase === "scan" ? "Scanning" : "Checked in"}</p>
              <button onClick={() => setRun((r) => r + 1)} className="link muted mt-3 text-xs">Scan again</button>
            </div>
            <motion.div aria-hidden className="absolute right-3 top-3 px-3 py-1.5 font-bold tracking-wider text-sm"
              style={{ border: "2px solid var(--accent2)", color: "var(--accent2)", borderRadius: 4, transformOrigin: "center", rotate: -12, background: "color-mix(in oklab, var(--bg2) 80%, transparent)" }}
              initial={false} animate={phase === "done" ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 2.2 }} transition={{ type: "spring", stiffness: 420, damping: 18 }}>
              ADMITTED
            </motion.div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
