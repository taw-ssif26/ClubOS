"use client";
import Link from "next/link";
import { use } from "react";
import { LeaderboardView } from "@/components/LeaderboardView";
import { RequireAuth } from "@/components/RequireAuth";

export default function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return (
    <RequireAuth>
      <div className="wrap py-16">
        <Link href={`/c/${slug}`} className="link muted">Back to the club</Link>
        <h1 className="display h-xl mt-3 mb-12">Leaderboard</h1>
        <LeaderboardView slug={slug} />
      </div>
    </RequireAuth>
  );
}
