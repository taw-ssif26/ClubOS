import type { Metadata } from "next";
import { Suspense } from "react";
import { UnsubscribeClient } from "@/components/UnsubscribeClient";

export const metadata: Metadata = { title: "Unsubscribe", robots: { index: false } };
export default function Page() { return <Suspense><UnsubscribeClient /></Suspense>; }
