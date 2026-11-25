"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { bytes, fmtDate } from "@/lib/format";
import { PlanCards } from "../PlanCards";
import { Button, Tag } from "../ui";
import { Meter } from "./Overview";
import type { Ctx } from "./ManageClient";

export function PlanTab({ slug, usage }: Ctx) {
  const [plans, setPlans] = useState<any[]>([]);
  const [reqs, setReqs] = useState<any[]>([]);
  useEffect(() => { api("/pricing").then((p) => setPlans(p.plans)); api(`/clubs/${slug}/upgrade-requests`).then(setReqs).catch(() => {}); }, [slug]);
  const L = usage.limits, U = usage.usage;
  const lapsed = usage.plan !== usage.effective_plan;
  return (
    <div className="space-y-14">
      <section className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div><p className="muted">Current plan</p><h2 className="display h-xl capitalize">{usage.effective_plan}</h2>
          {usage.expires_at && <p className="muted mt-2">{lapsed ? `Your ${usage.plan} plan expired on ${fmtDate(usage.expires_at)}. Nothing was deleted; new additions are limited to the free plan.` : `Renews by ${fmtDate(usage.expires_at)}`}</p>}
          <div className="mt-6"><Button href={`/upgrade?plan=${usage.effective_plan === "free" ? "pro" : usage.plan}`} variant="primary">{usage.effective_plan === "free" ? "Upgrade" : "Renew or change plan"}</Button></div>
          {reqs.length > 0 && <ul className="mt-8 text-sm space-y-1">{reqs.map((r) => <li key={r.id}><span className="muted">{fmtDate(r.created_at)}</span> · {r.plan_key} × {r.months} mo <Tag>{r.status}</Tag></li>)}</ul>}</div>
        <div className="panel p-6 space-y-5 self-start"><Meter label="Members" used={U.members} max={L.members} /><Meter label="Admin seats" used={U.admins} max={L.admins} /><Meter label="Active events" used={U.active_events} max={L.active_events} />
          <Meter label="Storage" used={U.storage_bytes} max={L.storage_mb === null ? null : L.storage_mb * 1048576} fmt={bytes} /></div>
      </section>
      <section><h2 className="display h-lg mb-8">Compare plans</h2><PlanCards plans={plans} /></section>
    </div>
  );
}
