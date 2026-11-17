"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Empty, Seal, Spinner, Tabs } from "../ui";
import { Reviews } from "../Reviews";
import { Overview } from "./Overview";
import { Members } from "./Members";
import { Events } from "./Events";
import { Posts } from "./Posts";
import { Email } from "./Email";
import { Settings } from "./Settings";
import { PlanTab } from "./PlanTab";
import { Activity, Analytics } from "./Insights";

export type Ctx = { slug: string; club: any; usage: any; can: (p: string) => boolean; reload: () => Promise<void>; go: (tab: string) => void };

export function ManageClient({ slug }: { slug: string }) {
  const [club, setClub] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState("overview");

  const reload = useCallback(async () => {
    try { const [c, u] = await Promise.all([api(`/clubs/${slug}`), api(`/clubs/${slug}/usage`)]); setClub(c); setUsage(u); } catch { setMissing(true); }
  }, [slug]);
  useEffect(() => { reload(); }, [reload]);

  if (missing) return <div className="wrap py-32"><Empty title="Club not found" body="You need to be an active member of this club." /></div>;
  if (!club || !usage) return <div className="wrap py-20"><Spinner /></div>;
  const perms: string[] = club.my_membership?.permissions || [];
  const can = (p: string) => perms.includes("*") || perms.includes(p);
  const ctx: Ctx = { slug, club, usage, can, reload, go: setTab };

  const all = [
    { id: "overview", label: "Overview", show: true },
    { id: "members", label: "Members", show: can("members.view") },
    { id: "events", label: "Events", show: can("events.manage") || can("attendance.manage") },
    { id: "posts", label: "Posts", show: can("posts.manage") },
    { id: "email", label: "Email", show: can("comms.send") },
    { id: "reviews", label: "Reviews", show: true },
    { id: "analytics", label: "Analytics", show: can("analytics.view") },
    { id: "settings", label: "Settings", show: can("club.settings") },
    { id: "plan", label: "Plan", show: can("club.settings") },
    { id: "activity", label: "Activity", show: can("audit.view") },
  ].filter((t) => t.show);

  return (
    <div className="wrap py-14">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div><p className="muted text-sm">{club.my_membership.role} · {usage.effective_plan} plan</p>
          <h1 className="display h-xl">{club.name} {club.verified && <Seal />}</h1></div>
        <Link href={`/c/${slug}`} className="link muted">View public page</Link>
      </div>
      <div className="mt-10"><Tabs id="manage" value={tab} onChange={setTab} tabs={all} /></div>
      <div className="mt-10">
        {tab === "overview" && <Overview {...ctx} />}
        {tab === "members" && <Members {...ctx} />}
        {tab === "events" && <Events {...ctx} />}
        {tab === "posts" && <Posts {...ctx} />}
        {tab === "email" && <Email {...ctx} />}
        {tab === "reviews" && <Reviews kind="clubs" slug={slug} canReply={can("club.settings")} />}
        {tab === "analytics" && <Analytics {...ctx} />}
        {tab === "settings" && <Settings {...ctx} />}
        {tab === "plan" && <PlanTab {...ctx} />}
        {tab === "activity" && <Activity {...ctx} />}
      </div>
    </div>
  );
}
