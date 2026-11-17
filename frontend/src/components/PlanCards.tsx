import Link from "next/link";
import { safeHref } from "@/lib/safe";
import { Tag } from "./ui";

export function PlanCards({ plans, contact }: { plans: any[]; contact?: string }) {
  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4 items-stretch">
      {plans.map((p) => {
        const custom = p.price_monthly === null;
        const href = p.key === "free" ? "/new-club" : custom ? `mailto:${contact || "hello@clubos.app"}?subject=ClubOS%20${p.name}` : `/upgrade?plan=${p.key}`;
        return (
          <article key={p.key} className="panel p-7 flex flex-col relative" style={p.highlighted ? { borderColor: "var(--accent)", background: "var(--bg3)" } : undefined}>
            {p.highlighted && <span className="absolute -top-3 left-6 tag" style={{ background: "var(--accent)", color: "var(--accent-fg)", borderColor: "var(--accent)" }}>Recommended</span>}
            <h3 className="display h-md">{p.name}</h3>
            <p className="muted text-sm mt-1 min-h-[2.6em]">{p.tagline}</p>
            <div className="mt-6 flex items-baseline gap-2 flex-wrap">
              {p.discounted_price != null && <span className="muted line-through text-lg">{p.price_label}</span>}
              <span className="display" style={{ fontSize: "2.6rem" }}>{p.discounted_price != null ? `৳${p.discounted_price.toLocaleString("en-IN")}` : p.price_label}</span>
              {!custom && <span className="muted text-sm">/month</span>}
            </div>
            {p.offer && <p className="text-sm mt-1" style={{ color: "var(--accent)" }}>{p.offer.badge ? `${p.offer.badge}: ` : ""}{p.offer.title}</p>}
            <Link href={href} className={`btn mt-6 ${p.highlighted ? "btn-primary" : ""}`}>{p.cta_label}</Link>
            <ul className="mt-7 space-y-2.5 text-[.93rem]">
              {p.features.map((f: any, i: number) => (
                <li key={i} className="flex gap-2.5 items-start" style={{ opacity: f.status === "soon" ? .72 : 1 }}>
                  <span aria-hidden className="mt-[.45em] w-1.5 h-1.5 shrink-0" style={{ background: f.status === "soon" ? "transparent" : "var(--accent)", border: "1px solid var(--accent)", borderRadius: "50%" }} />
                  <span>{f.label} {f.status === "soon" && <Tag kind="soon">Soon</Tag>}</span>
                </li>
              ))}
            </ul>
          </article>
        );
      })}
    </div>
  );
}
