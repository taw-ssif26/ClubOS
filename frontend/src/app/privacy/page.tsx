import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { sget } from "@/lib/server";

export const metadata: Metadata = { title: "Privacy Policy" };
export default async function Page() { const c = await sget("/content"); return <LegalPage doc={c?.["legal.privacy"]} />; }
