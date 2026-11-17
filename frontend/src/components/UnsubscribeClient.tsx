"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "./ui";

export function UnsubscribeClient() {
  const sp = useSearchParams();
  const [state, setState] = useState<"ask" | "done" | "bad">("ask");
  const [club, setClub] = useState("");
  const go = async () => {
    try { const r = await api("/unsubscribe", { method: "POST", body: { u: sp.get("u"), c: sp.get("c"), t: sp.get("t") } }); setClub(r.club || "this club"); setState("done"); } catch { setState("bad"); }
  };
  return (
    <div className="wrap py-28 max-w-2xl">
      {state === "ask" && <><h1 className="display h-xl">Stop these emails?</h1><p className="lede mt-5">You&apos;ll stop receiving announcements and campaigns from this club. Account and event confirmation emails still arrive.</p><div className="mt-9"><Button variant="primary" onClick={go}>Unsubscribe</Button></div></>}
      {state === "done" && <><h1 className="display h-xl">Done.</h1><p className="lede mt-5">You won&apos;t get email from {club} any more.</p></>}
      {state === "bad" && <><h1 className="display h-xl">That link didn&apos;t work.</h1><p className="lede mt-5">It may be incomplete. Use the link from the most recent email.</p></>}
    </div>
  );
}
