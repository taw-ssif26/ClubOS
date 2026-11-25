import type { MetadataRoute } from "next";
import { SITE, sget } from "@/lib/server";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [clubs, events] = await Promise.all([sget<any[]>("/discover/clubs?limit=50&sort=name", 300), sget<any[]>("/discover/events?limit=50", 300)]);
  return [
    { url: SITE, changeFrequency: "weekly", priority: 1 }, { url: `${SITE}/pricing` }, { url: `${SITE}/discover`, changeFrequency: "daily" },
    ...(clubs || []).map((c) => ({ url: `${SITE}/c/${c.slug}`, changeFrequency: "weekly" as const })),
    ...(events || []).map((e) => ({ url: `${SITE}/e/${e.slug}`, lastModified: e.starts_at })),
  ];
}
