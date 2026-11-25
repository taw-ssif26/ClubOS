import type { Metadata } from "next";
import { Suspense } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { UpgradeClient } from "@/components/UpgradeClient";

export const metadata: Metadata = { title: "Upgrade", robots: { index: false } };
export default function Page() { return <RequireAuth><Suspense><UpgradeClient /></Suspense></RequireAuth>; }
