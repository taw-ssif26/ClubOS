"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { locateMe, MODE_LABEL, usePlaces } from "@/lib/places";
import { useToast } from "@/lib/toast";
import { ClubCard, TicketCard } from "./Cards";
import { Button, Empty, Input, Select, Spinner, Tabs } from "./ui";

const CATS = ["technology", "science", "arts", "culture", "sports", "business", "debate", "social", "academic", "media", "general"];

export function DiscoverClient() {
  const sp = useSearchParams();
  const { user } = useAuth();
  const places = usePlaces();
  const toast = useToast();
  const [tab, setTab] = useState("clubs");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [mode, setMode] = useState("");
  const [sort, setSort] = useState("rating");
  const [here, setHere] = useState<{ lat: number; lng: number; label: string } | null>(null);   // "near me" origin chosen on this page
  const [rows, setRows] = useState<any[] | null>(null);
  const inst = sp.get("institution") || "";
  const saved = user?.latitude != null ? { lat: user.latitude, lng: user.longitude as number, label: user.place_name || "your saved location" } : null;
  const origin = here || saved;
  const nearby = Boolean(origin) && sort === "nearest";

  const pick = async (id: string) => {
    if (id === "gps") { try { const r = await locateMe(); setHere({ ...r, label: "your current position" }); setSort("nearest"); } catch (e: any) { toast(e.message, "err"); } return; }
    const p = places.find((x) => x.id === id);
    if (p) { setHere({ lat: p.lat, lng: p.lng, label: p.name }); setSort("nearest"); } else { setHere(null); if (sort === "nearest") setSort("rating"); }
  };

  useEffect(() => {
    setRows(null);
    const t = setTimeout(() => {
      const p = new URLSearchParams();
      if (q.trim()) p.set("q", q.trim());
      if (cat) p.set("category", cat);
      if (mode) p.set("mode", mode);
      if (nearby && origin) { p.set("lat", String(origin.lat)); p.set("lng", String(origin.lng)); p.set("sort", "nearest"); }
      else if (tab === "clubs") p.set("sort", sort === "nearest" ? "rating" : sort);
      if (tab === "clubs" && inst) p.set("institution", inst);
      api(`/discover/${tab}?${p}`).then(setRows).catch(() => setRows([]));
    }, 250); // debounce typing
    return () => clearTimeout(t);
  }, [tab, q, cat, mode, sort, inst, here, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mt-12">
      <Tabs id="disc" value={tab} onChange={setTab} tabs={[{ id: "clubs", label: "Clubs" }, { id: "events", label: "Happening and upcoming" }]} />
      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr_1fr_1fr]">
        <Input type="search" aria-label="Search" placeholder={tab === "clubs" ? "Search clubs" : "Search events"} value={q} onChange={(e) => setQ(e.target.value)} />
        <Select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{CATS.map((c) => <option key={c} value={c}>{c}</option>)}</Select>
        <Select aria-label="How it takes place" value={mode} onChange={(e) => setMode(e.target.value)}><option value="">On-site, online or hybrid</option>{Object.entries(MODE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select>
        <Select aria-label="Near" value={here ? "" : ""} onChange={(e) => pick(e.target.value)}>
          <option value="">{here ? `Near ${here.label}` : saved ? `Near ${saved.label}` : "Near me…"}</option>
          <option value="gps">Use my current position</option>
          {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
        <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          {tab === "clubs" && <option value="rating">Top rated</option>}{tab === "clubs" && <option value="name">A to Z</option>}
          {tab === "events" && <option value="soonest">Soonest</option>}
          <option value="nearest" disabled={!origin}>{origin ? "Nearest first" : "Nearest (pick a place)"}</option>
        </Select>
      </div>
      {origin && nearby && <p className="muted text-sm mt-4">Showing the closest first, measured from {origin.label}. Online ones follow.{here && <> <button className="link" onClick={() => { setHere(null); setSort(tab === "clubs" ? "rating" : "soonest"); }}>Reset</button></>}</p>}
      {!user && !origin && <p className="muted text-sm mt-4">Tip: pick a place above, or <a className="link" href="/login?next=/discover">sign in</a> and save your location to see what's nearest.</p>}
      <div className="mt-12">
        {rows === null ? <Spinner /> : rows.length === 0 ? <Empty title="Nothing matches yet" body="Try a different search or filter, or start the club you wish existed." action={<Button href="/new-club">Start a club</Button>} />
          : <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">{rows.map((r) => tab === "clubs" ? <ClubCard key={r.slug} c={r} /> : <TicketCard key={r.slug} e={r} />)}</div>}
      </div>
    </div>
  );
}
