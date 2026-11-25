"use client";
import { Field, Input, Select, Textarea } from "./ui";

export type FieldDef = { id: string; type: string; label: string; required?: boolean; options?: string[]; show_if?: { field: string; equals: any } };

export const visible = (f: FieldDef, v: Record<string, any>) => !f.show_if || v[f.show_if.field] === f.show_if.equals;

export function FormRenderer({ fields, value, onChange, errors = {} }: { fields: FieldDef[]; value: Record<string, any>; onChange: (v: Record<string, any>) => void; errors?: Record<string, string> }) {
  const set = (id: string, v: any) => onChange({ ...value, [id]: v });
  return (
    <div className="space-y-6">
      {fields.filter((f) => visible(f, value)).map((f) => {
        const lbl = `${f.label}${f.required ? " *" : ""}`;
        const err = errors[f.id];
        switch (f.type) {
          case "textarea": return <Field key={f.id} label={lbl} error={err}><Textarea value={value[f.id] || ""} onChange={(e) => set(f.id, e.target.value)} /></Field>;
          case "number": return <Field key={f.id} label={lbl} error={err}><Input type="number" value={value[f.id] ?? ""} onChange={(e) => set(f.id, e.target.value === "" ? "" : Number(e.target.value))} /></Field>;
          case "date": return <Field key={f.id} label={lbl} error={err}><Input type="date" value={value[f.id] || ""} onChange={(e) => set(f.id, e.target.value)} /></Field>;
          case "email": case "phone": return <Field key={f.id} label={lbl} error={err}><Input type={f.type === "email" ? "email" : "tel"} value={value[f.id] || ""} onChange={(e) => set(f.id, e.target.value)} /></Field>;
          case "dropdown": return <Field key={f.id} label={lbl} error={err}><Select value={value[f.id] || ""} onChange={(e) => set(f.id, e.target.value)}><option value="">Choose…</option>{f.options?.map((o) => <option key={o}>{o}</option>)}</Select></Field>;
          case "radio": return (
            <fieldset key={f.id}><legend className="label">{lbl}</legend>
              <div className="flex flex-wrap gap-x-6 gap-y-2 mt-1">{f.options?.map((o) => <label key={o} className="flex items-center gap-2"><input type="radio" className="check" name={f.id} checked={value[f.id] === o} onChange={() => set(f.id, o)} />{o}</label>)}</div>
              {err && <span className="err block">{err}</span>}</fieldset>);
          case "checkbox": return (
            <fieldset key={f.id}><legend className="label">{lbl}</legend>
              <div className="flex flex-wrap gap-x-6 gap-y-2 mt-1">{f.options?.map((o) => { const cur: string[] = value[f.id] || []; return <label key={o} className="flex items-center gap-2"><input type="checkbox" className="check" checked={cur.includes(o)} onChange={(e) => set(f.id, e.target.checked ? [...cur, o] : cur.filter((x) => x !== o))} />{o}</label>; })}</div>
              {err && <span className="err block">{err}</span>}</fieldset>);
          case "agreement": return <div key={f.id}><label className="flex items-start gap-2"><input type="checkbox" className="check mt-1" checked={value[f.id] === true} onChange={(e) => set(f.id, e.target.checked)} /><span>{lbl}</span></label>{err && <span className="err block">{err}</span>}</div>;
          default: return <Field key={f.id} label={lbl} error={err}><Input value={value[f.id] || ""} onChange={(e) => set(f.id, e.target.value)} /></Field>;
        }
      })}
    </div>
  );
}
