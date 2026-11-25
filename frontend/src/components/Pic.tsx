"use client";
import { useState } from "react";

/** An image that never shows the browser's broken-image icon: if it fails to load, the fallback (or nothing) renders. */
export function Pic({ src, alt = "", className, style, fallback = null }: { src?: string | null; alt?: string; className?: string; style?: React.CSSProperties; fallback?: React.ReactNode }) {
  const [bad, setBad] = useState(false);
  if (!src || bad) return <>{fallback}</>;
  return <img src={src} alt={alt} className={className} style={style} onError={() => setBad(true)} loading="lazy" />;
}
