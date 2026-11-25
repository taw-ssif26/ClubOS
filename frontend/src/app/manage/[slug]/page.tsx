import type { Metadata } from "next";
import { ManageClient } from "@/components/manage/ManageClient";
import { RequireAuth } from "@/components/RequireAuth";

export const metadata: Metadata = { title: "Club dashboard", robots: { index: false } };
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <RequireAuth><ManageClient slug={slug} /></RequireAuth>;
}
