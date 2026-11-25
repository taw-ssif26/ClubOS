import type { Metadata } from "next";
import { Suspense } from "react";
import { DiscoverClient } from "@/components/DiscoverClient";
import { sget } from "@/lib/server";

export const metadata: Metadata = { title: "Discover clubs and events", description: "Find clubs and events open to everyone, ranked by what members think." };

export default async function Discover() {
  const c = await sget("/content");
  const p = c?.["discover.page"];
  return (
    <div className="wrap py-20">
      <h1 className="display h-xl">{p?.title || "Discover"}</h1>
      <p className="lede mt-6">{p?.subtitle}</p>
      <Suspense><DiscoverClient /></Suspense>
    </div>
  );
}
