/** Readable foreground (near-black or near-white) for an arbitrary #RRGGBB background. */
export function fgOn(hex: string): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return "#111";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.38 ? "#0b0b0b" : "#fafaf5";
}
export const FONT_MAP: Record<string, { family: string; weight: number; spacing: string }> = {
  "display-serif": { family: "var(--font-display)", weight: 500, spacing: "-.025em" },
  grotesk: { family: "'Hanken Grotesk Variable', system-ui, sans-serif", weight: 700, spacing: "-.04em" },
  humanist: { family: "'Hanken Grotesk Variable', system-ui, sans-serif", weight: 600, spacing: "-.015em" },
  mono: { family: "'JetBrains Mono Variable', ui-monospace, monospace", weight: 700, spacing: "-.05em" },
};
