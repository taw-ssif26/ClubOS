import Link from "next/link";
import { HeroTicket } from "@/components/HeroTicket";
import { LineReveal } from "@/components/LineReveal";
import { PlanCards } from "@/components/PlanCards";
import { Button, Stars } from "@/components/ui";
import { safeHref } from "@/lib/safe";
import { sget } from "@/lib/server";

export default async function Home() {
  const [c, pricing, reviews] = await Promise.all([sget("/content"), sget("/pricing"), sget("/reviews/featured")]);
  const hero = c?.["home.hero"];
  if (!hero) return <div className="wrap py-40"><p className="display h-lg">We&apos;ll be right back.</p><p className="lede mt-4">The service is starting up. Refresh in a moment.</p></div>;
  const proof: string[] = c["home.proof"]?.items || [];
  const feats = c["home.features"], how = c["home.how"], prob = c["home.problem"], cta = c["home.cta"];
  return (
    <>
      <section className="wrap pt-16 pb-24 grid grid-cols-1 gap-14 lg:grid-cols-[1.25fr_.75fr] items-center min-h-[78vh]">
        <div>
          <h1 className="display h-xl"><LineReveal text={hero.title} delay={.1} /></h1>
          <p className="lede mt-8">{hero.subtitle}</p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Button href={safeHref(hero.cta_primary?.href, "/new-club")} variant="primary">{hero.cta_primary?.label}</Button>
            <Button href={safeHref(hero.cta_secondary?.href, "/discover")}>{hero.cta_secondary?.label}</Button>
          </div>
        </div>
        {hero.ticket && <HeroTicket t={hero.ticket} />}
      </section>

      <section aria-label="What's included" className="border-y border-line py-6 overflow-hidden">
        <div className="marquee" aria-hidden>
          {[...proof, ...proof].map((p, i) => <span key={i} className="display h-md px-8 whitespace-nowrap flex items-center gap-16">{p}<span style={{ color: "var(--accent)" }}>✦</span></span>)}
        </div>
        <p className="sr-only">{proof.join(", ")}</p>
      </section>

      <section className="wrap py-28 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <h2 className="display h-lg">{prob?.title}</h2>
        <p className="lede self-end" style={{ color: "var(--fg)", opacity: .78 }}>{prob?.body}</p>
      </section>

      <section className="wrap pb-28">
        <h2 className="display h-lg max-w-3xl">{feats?.title}</h2>
        <div className="mt-14 border-t border-line">
          {(feats?.items || []).map((f: any) => (
            <div key={f.title} className="sheen group grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr] py-8 border-b border-line transition-colors hover:bg-[var(--bg2)] px-2 -mx-2">
              <h3 className="display h-md transition-transform duration-500 group-hover:translate-x-2">{f.title}</h3>
              <p className="muted max-w-[52ch]">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-24" style={{ background: "var(--bg2)", borderBlock: "1px solid var(--line)" }}>
        <div className="wrap">
          <h2 className="display h-lg max-w-3xl">{how?.title}</h2>
          <ol className="mt-14 grid grid-cols-1 gap-10 md:grid-cols-3">
            {(how?.steps || []).map((s: any, i: number) => (
              <li key={s.title}>
                <span className="display" style={{ fontSize: "5.5rem", color: "var(--accent)", lineHeight: 1 }}>{i + 1}</span>
                <h3 className="display h-md mt-3">{s.title}</h3>
                <p className="muted mt-2">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {reviews?.length > 0 && (
        <section className="wrap py-28">
          <h2 className="display h-lg">{c["home.reviews"]?.title}</h2>
          <div className="mt-12 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {reviews.map((r: any) => (
              <figure key={r.id} className="panel sheen p-6 flex flex-col">
                <Stars value={r.rating} />
                <blockquote className="mt-4 flex-1" style={{ fontSize: "1.05rem" }}>{r.title && <strong className="block mb-1">{r.title}</strong>}{r.body}</blockquote>
                <figcaption className="muted text-sm mt-5">{r.user.full_name} on <Link className="link" href={`/c/${r.club.slug}`}>{r.club.name}</Link></figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {pricing?.plans && (
        <section className="wrap py-10 pb-28">
          <div className="flex items-end justify-between gap-6 flex-wrap mb-12">
            <h2 className="display h-lg max-w-2xl">{c["pricing.page"]?.title}</h2>
            <Link href="/pricing" className="link">Compare every feature</Link>
          </div>
          <PlanCards plans={pricing.plans.filter((p: any) => p.key === "free" || p.key === "pro")} contact={c["site.brand"]?.contact_email} />
        </section>
      )}

      <section className="wrap pb-10">
        <div className="panel p-10 md:p-16 text-center" style={{ background: "var(--bg3)" }}>
          <h2 className="display h-xl" style={{ fontSize: "clamp(2.4rem,5.5vw,4.6rem)" }}>{cta?.title}</h2>
          <p className="lede mx-auto mt-5">{cta?.subtitle}</p>
          <div className="mt-9"><Button href="/new-club" variant="primary">{cta?.button}</Button></div>
        </div>
      </section>
    </>
  );
}
