import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/AuthForm";

export const metadata: Metadata = { title: "Forgot password", robots: { index: false } };
export default function Page() { return <Suspense><AuthForm kind="forgot" /></Suspense>; }
