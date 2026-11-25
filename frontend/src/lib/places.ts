"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type Place = { id: string; name: string; division: string; lat: number; lng: number };
let cache: Place[] | null = null;

export function usePlaces(): Place[] {
  const [p, setP] = useState<Place[]>(cache || []);
  useEffect(() => { if (!cache) api<Place[]>("/places").then((r) => { cache = r; setP(r); }).catch(() => {}); }, []);
  return p;
}

export type Loc = { mode?: string; place_name?: string | null; address?: string | null; latitude?: number | null; longitude?: number | null };
/** "Notre Dame College, Motijheel" + "Motijheel, Dhaka" should read "Notre Dame College, Motijheel", not repeat the place. */
export function placeText(address?: string | null, placeName?: string | null): string {
  const short = (placeName || "").split(",")[0].trim().toLowerCase();
  return address && short && address.toLowerCase().includes(short) ? address : [address, placeName].filter(Boolean).join(", ");
}
export const MODE_LABEL: Record<string, string> = { onsite: "On-site", online: "Online", hybrid: "Hybrid" };

/** Opens a map app/site: no embedded third-party map, so no tracking script on our pages. */
export function mapsUrl(l: Loc): string | null {
  if (l.latitude != null && l.longitude != null) return `https://www.google.com/maps/search/?api=1&query=${l.latitude},${l.longitude}`;
  const q = placeText(l.address, l.place_name);
  return q ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}` : null;
}

export function locationLine(l?: Loc | null): string {
  if (!l) return "";
  if (l.mode === "online") return "Online";
  return [l.mode === "hybrid" ? "Hybrid" : "", placeText(l.address, l.place_name)].filter(Boolean).join(" · ");
}

export function locateMe(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Your browser can't share its location."));
    navigator.geolocation.getCurrentPosition((p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      (e) => reject(new Error(e.code === 1 ? "Location permission was denied. Pick a place from the list instead." : "Couldn't get your location. Pick a place from the list instead.")),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 });
  });
}
