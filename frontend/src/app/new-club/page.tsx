import type { Metadata } from "next";
import { NewClub } from "@/components/NewClub";
import { RequireAuth } from "@/components/RequireAuth";

export const metadata: Metadata = { title: "Start a club", robots: { index: false } };
export default function Page() { return <RequireAuth><NewClub /></RequireAuth>; }
