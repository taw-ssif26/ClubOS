"use client";
import { Button, Input, Select, Textarea } from "./ui";
import type { FieldDef } from "./FormRenderer";

const TYPES = ["text", "textarea", "number", "email", "phone", "dropdown", "radio", "checkbox", "date", "agreement"];
const CHOICE = ["dropdown", "radio", "checkbox"];
const idOf = (label: string, taken: string[]) => {
  const base = (label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "field").replace(/^(\d)/, "f$1").slice(0, 30);
  let id = base, n = 2;
  while (taken.includes(id)) id = `${base}_${n++}`;
  return id;
};

/** Visual editor for registration/application forms. Ids are generated and then stay stable. */
export function FieldBuilder({ fields, onChange, canConditions }: { fields: FieldDef[]; onChange: (f: FieldDef[]) => void; canConditions: boolean }) {
  const upd = (i: number, patch: Partial<FieldDef>) => onChange(fields.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  const move = (i: number, d: number) => { const a = [...fields]; const j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; onChange(a); };
  const add = () => onChange([...fields, { id: idOf("question", fields.map((f) => f.id)), type: "text", label: "New question", required: false }]);
  return (
    <div className="space-y-3">
      {fields.map((f, i) => {
        const earlier = fields.slice(0, i).filter((x) => CHOICE.includes(x.type) || x.type === "agreement");
        const dep = f.show_if && fields.find((x) => x.id === f.show_if!.field);
        return (
          <div key={f.id} className="panel p-4 space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_150px_auto]">
              <Input aria-label="Question" value={f.label} onChange={(e) => upd(i, { label: e.target.value })} />
              <Select aria-label="Type" value={f.type} onChange={(e) => upd(i, { type: e.target.value, options: CHOICE.includes(e.target.value) ? f.options?.length ? f.options : ["Option 1", "Option 2"] : undefined })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" className="check" checked={!!f.required} onChange={(e) => upd(i, { required: e.target.checked })} />Required</label>
                <Button size="sm" onClick={() => move(i, -1)} aria-label="Move up" disabled={i === 0}>↑</Button>
                <Button size="sm" onClick={() => move(i, 1)} aria-label="Move down" disabled={i === fields.length - 1}>↓</Button>
                <Button size="sm" variant="danger" onClick={() => onChange(fields.filter((_, j) => j !== i).map((x) => (x.show_if?.field === f.id ? { ...x, show_if: undefined } : x)))} aria-label="Remove">✕</Button>
              </div>
            </div>
            {CHOICE.includes(f.type) && <Textarea aria-label="Options, one per line" style={{ minHeight: "5rem" }} value={(f.options || []).join("\n")} onChange={(e) => upd(i, { options: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })} placeholder="One option per line" />}
            {canConditions && earlier.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="muted">Show only when</span>
                <Select className="!w-auto" value={f.show_if?.field || ""} onChange={(e) => upd(i, { show_if: e.target.value ? { field: e.target.value, equals: f.show_if?.equals ?? "" } : undefined })}>
                  <option value="">always</option>{earlier.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </Select>
                {f.show_if && <><span className="muted">is</span>
                  {dep?.type === "agreement" ? <Select className="!w-auto" value={String(f.show_if.equals)} onChange={(e) => upd(i, { show_if: { ...f.show_if!, equals: e.target.value === "true" } })}><option value="true">checked</option></Select>
                    : <Select className="!w-auto" value={String(f.show_if.equals)} onChange={(e) => upd(i, { show_if: { ...f.show_if!, equals: e.target.value } })}><option value="">choose…</option>{dep?.options?.map((o) => <option key={o}>{o}</option>)}</Select>}</>}
              </div>
            )}
          </div>
        );
      })}
      <Button size="sm" onClick={add}>Add question</Button>
    </div>
  );
}
