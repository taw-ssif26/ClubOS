import type { Metadata } from "next";
import { PlanCards } from "@/components/PlanCards";
import { Faq } from "@/components/Faq";
import { sget } from "@/lib/server";

export const metadata: Metadata = { title: "Pricing", description: "Free to run a club. Paid plans for scale and automation. Prices in Bangladeshi taka." };

export default async function Pricing() {
  const [c, pricing] = await Promise.all([sget("/content"), sget("/pricing")]);
  const page = c?.["pricing.page"];
  return (
    <div className="wrap py-20">
      <h1 className="display h-xl max-w-5xl">{page?.title || "Pricing"}</h1>
      <p className="lede mt-6">{page?.subtitle}</p>
      <div className="mt-16">{pricing?.plans ? <PlanCards plans={pricing.plans} contact={c?.["site.brand"]?.contact_email} /> : <p className="muted">Pricing is unavailable right now.</p>}</div>
      {page?.billing_note && <p className="muted mt-8 max-w-2xl">{page.billing_note}</p>}
      {page?.faq?.length > 0 && <div className="mt-24 max-w-3xl"><h2 className="display h-lg mb-8">Questions</h2><Faq items={page.faq} /></div>}
    </div>
  );
}
