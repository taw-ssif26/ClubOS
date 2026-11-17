"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ClubCard, TicketCard } from "./Cards";
import { Input, Select, Spinner, Tabs, Empty } from "./ui";

const CATS = ["technology", "science", "arts", "culture", "sports", "business", "debate", "social", "academic", "media", "general"];

export function DiscoverClient() {
  const sp = useSearchParams();
  const [tab, setTab] = useState("clubs");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [sort, setSort] = useState("rating");
  const [rows, setRows] = useState<any[] | null>(null);
  const inst = sp.get("institution") || "";

  useEffect(() => {
    setRows(null);
    const t = setTimeout(() => {
      const p = new URLSearchParams();
      if (q.trim()) p.set("q", q.trim());
      if (cat) p.set("category", cat);
      if (tab === "clubs") { p.set("sort", sort); if (inst) p.set("institution", inst); }
      api(`/discover/${tab}?${p}`).then(setRows).catch(() => setRows([]));
    }, 250); // debounce typing
    return () => clearTimeout(t);
  }, [tab, q, cat, sort, inst]);

  return (
    <div className="mt-12">
      <Tabs id="disc" value={tab} onChange={setTab} tabs={[{ id: "clubs", label: "Clubs" }, { id: "events", label: "Upcoming events" }]} />
      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-[1fr_200px_200px]">
        <Input type="search" aria-label="Search" placeholder={tab === "clubs" ? "Search clubs" : "Search events"} value={q} onChange={(e) => setQ(e.target.value)} />
        <Select aria-label="Category" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{CATS.map((c) => <option key={c} value={c} className="capitalize">{c}</option>)}</Select>
        {tab === "clubs" && <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}><option value="rating">Top rated</option><option value="name">A to Z</option></Select>}
      </div>
      <div className="mt-12">
        {rows === null ? <Spinner /> : rows.length === 0 ? <Empty title="Nothing matches yet" body="Try a different search, or start the club you wish existed." />
          : <div className={`grid grid-cols-1 gap-6 md:grid-cols-2 ${tab === "events" ? "xl:grid-cols-3" : "xl:grid-cols-3"}`}>{rows.map((r) => tab === "clubs" ? <ClubCard key={r.slug} c={r} /> : <TicketCard key={r.slug} e={r} />)}</div>}
      </div>
    </div>
  );
}
