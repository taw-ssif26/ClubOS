import type { Metadata } from "next";
import { AdminClient } from "@/components/admin/AdminClient";
import { RequireAuth } from "@/components/RequireAuth";

export const metadata: Metadata = { title: "Super admin", robots: { index: false } };
export default function Page() { return <RequireAuth admin><AdminClient /></RequireAuth>; }
