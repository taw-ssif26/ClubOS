"use client";
import { useState } from "react";
import { locateMe, MODE_LABEL, usePlaces } from "@/lib/places";
import { useToast } from "@/lib/toast";
import { Button, Field, Input, Select } from "./ui";

export type LocValue = { location_mode?: string; place: string; address?: string; latitude?: number | null; longitude?: number | null };

/** Club, event and personal locations share this picker. Online items have no physical place. */
export function LocationPicker({ value, onChange, withMode = true, withAddress = true, hint }: { value: LocValue; onChange: (v: LocValue) => void; withMode?: boolean; withAddress?: boolean; hint?: string }) {
  const places = usePlaces();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const online = withMode && value.location_mode === "online";
  const divisions = Array.from(new Set(places.map((p) => p.division)));
  const useHere = async () => {
    setBusy(true);
    try { const { lat, lng } = await locateMe(); onChange({ ...value, latitude: lat, longitude: lng }); toast("Position captured"); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-5">
      {withMode && (
        <Field label="How does it take place?">
          <Select value={value.location_mode || "onsite"} onChange={(e) => onChange({ ...value, location_mode: e.target.value })}>
            {Object.entries(MODE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
        </Field>
      )}
      {!online && (<>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="City or area" hint={hint}>
            <Select value={value.place} onChange={(e) => onChange({ ...value, place: e.target.value, latitude: null, longitude: null })}>
              <option value="">Not set</option>
              {divisions.map((d) => <optgroup key={d} label={`${d} division`}>{places.filter((p) => p.division === d).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>)}
            </Select>
          </Field>
          {withAddress && <Field label="Venue or address (optional)"><Input maxLength={200} value={value.address || ""} onChange={(e) => onChange({ ...value, address: e.target.value })} /></Field>}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Button size="sm" loading={busy} onClick={useHere}>Use my current position</Button>
          {value.latitude != null && <span className="muted">Exact position set <button className="link" onClick={() => onChange({ ...value, latitude: null, longitude: null })}>clear</button></span>}
        </div>
      </>)}
      {online && <p className="muted text-sm">Online items appear for everyone, wherever they are.</p>}
    </div>
  );
}

/** The API treats "" as "clear this". */
export const locPayload = (v: LocValue, withMode = true) => ({
  ...(withMode ? { location_mode: v.location_mode || "onsite" } : {}),
  place: v.place || "", ...(v.address !== undefined ? { address: v.address || "" } : {}),
  ...(v.latitude != null ? { latitude: v.latitude, longitude: v.longitude } : {}),
});
