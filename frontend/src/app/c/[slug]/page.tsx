import type { Metadata } from "next";
import { ClubView } from "@/components/ClubView";
import { SITE, sget } from "@/lib/server";

type P = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { slug } = await params;
  const d = await sget(`/public/clubs/${slug}`);
  if (!d) return { title: "Club" };
  const c = d.club;
  return { title: c.name, description: c.description?.slice(0, 160) || `${c.name} on ClubOS`, alternates: { canonical: `${SITE}/c/${slug}` },
    openGraph: { title: c.name, description: c.description?.slice(0, 160), images: c.cover_url || c.logo_url ? [c.cover_url || c.logo_url] : undefined } };
}

export default async function ClubPage({ params }: P) {
  const { slug } = await params;
  const d = await sget(`/public/clubs/${slug}`);
  const ld = d && { "@context": "https://schema.org", "@type": "Organization", name: d.club.name, url: `${SITE}/c/${slug}`, description: d.club.description,
    ...(d.club.rating?.count ? { aggregateRating: { "@type": "AggregateRating", ratingValue: d.club.rating.average, reviewCount: d.club.rating.count } } : {}) };
  return (<>{ld && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />}<ClubView slug={slug} initial={d} /></>);
}
