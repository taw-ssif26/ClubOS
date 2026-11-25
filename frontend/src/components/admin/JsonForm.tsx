"use client";
import { Button, Field, Input, Textarea } from "../ui";

const human = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const blank = (t: any): any => (Array.isArray(t) ? [] : t && typeof t === "object" ? Object.fromEntries(Object.entries(t).map(([k, v]) => [k, blank(v)])) : typeof t === "number" ? 0 : typeof t === "boolean" ? false : "");

/** Edits any JSON shape: strings, numbers, booleans, nested objects, and repeatable lists. This is what makes all site copy editable. */
export function JsonForm({ value, onChange, label }: { value: any; onChange: (v: any) => void; label?: string }) {
  if (typeof value === "string") {
    const long = value.length > 90 || value.includes("\n");
    return <Field label={label}>{long ? <Textarea value={value} onChange={(e) => onChange(e.target.value)} /> : <Input value={value} onChange={(e) => onChange(e.target.value)} />}</Field>;
  }
  if (typeof value === "number") return <Field label={label}><Input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} /></Field>;
  if (typeof value === "boolean") return <label className="flex items-center gap-2"><input className="check" type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />{label}</label>;
  if (Array.isArray(value)) {
    const move = (i: number, d: number) => { const a = [...value]; const j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; onChange(a); };
    const primitive = value.length === 0 || typeof value[0] !== "object";
    return (
      <div className="space-y-3">
        {label && <p className="label">{label}</p>}
        {value.map((item, i) => (
          <div key={i} className={primitive ? "flex gap-2 items-end" : "panel p-4 space-y-4"}>
            <div className="flex-1"><JsonForm value={item} onChange={(v) => onChange(value.map((x, j) => (j === i ? v : x)))} /></div>
            <div className="flex gap-1.5"><Button size="sm" onClick={() => move(i, -1)} aria-label="Move up">↑</Button><Button size="sm" onClick={() => move(i, 1)} aria-label="Move down">↓</Button><Button size="sm" variant="danger" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label="Remove">✕</Button></div>
          </div>
        ))}
        <Button size="sm" onClick={() => onChange([...value, value.length ? blank(value[0]) : ""])}>Add item</Button>
      </div>
    );
  }
  if (value && typeof value === "object") {
    return (
      <div className="space-y-5">
        {label && <p className="font-semibold">{label}</p>}
        {Object.entries(value).map(([k, v]) => <JsonForm key={k} label={human(k)} value={v} onChange={(nv) => onChange({ ...value, [k]: nv })} />)}
      </div>
    );
  }
  return null;
}
