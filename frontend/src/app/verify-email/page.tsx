import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/AuthForm";

export const metadata: Metadata = { title: "Verify email", robots: { index: false } };
export default function Page() { return <Suspense><AuthForm kind="verify" /></Suspense>; }
