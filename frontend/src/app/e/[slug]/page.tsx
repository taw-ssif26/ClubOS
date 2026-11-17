import type { Metadata } from "next";
import { EventView } from "@/components/EventView";
import { SITE, sget } from "@/lib/server";

type P = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { slug } = await params;
  const e = await sget(`/events/${slug}`);
  if (!e) return { title: "Event" };
  return { title: e.title, description: e.description?.slice(0, 160) || `${e.title} by ${e.club.name}`, alternates: { canonical: `${SITE}/e/${slug}` },
    openGraph: { title: e.title, description: e.description?.slice(0, 160), images: e.banner_url ? [e.banner_url] : undefined } };
}

export default async function EventPage({ params }: P) {
  const { slug } = await params;
  const e = await sget(`/events/${slug}`);
  const ld = e && { "@context": "https://schema.org", "@type": "Event", name: e.title, startDate: e.starts_at, endDate: e.ends_at || undefined, description: e.description,
    eventStatus: e.status === "cancelled" ? "https://schema.org/EventCancelled" : "https://schema.org/EventScheduled",
    eventAttendanceMode: e.is_online ? "https://schema.org/OnlineEventAttendanceMode" : "https://schema.org/OfflineEventAttendanceMode",
    location: e.venue ? { "@type": "Place", name: e.venue } : undefined, organizer: { "@type": "Organization", name: e.club.name, url: `${SITE}/c/${e.club.slug}` } };
  return (<>{ld && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />}<EventView slug={slug} initial={e} /></>);
}
