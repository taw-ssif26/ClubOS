"use client";
import { Button } from "@/components/ui";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return <div className="wrap py-32"><p className="display h-xl">Something broke.</p><p className="lede mt-5">It&apos;s on our side. Try again, and if it keeps happening let us know.</p><div className="mt-8"><Button variant="primary" onClick={reset}>Try again</Button></div></div>;
}
