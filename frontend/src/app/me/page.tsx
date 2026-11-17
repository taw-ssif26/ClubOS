import type { Metadata } from "next";
import { Suspense } from "react";
import { MeClient } from "@/components/MeClient";
import { RequireAuth } from "@/components/RequireAuth";

export const metadata: Metadata = { title: "My space", robots: { index: false } };
export default function Me() { return <RequireAuth><Suspense><MeClient /></Suspense></RequireAuth>; }
