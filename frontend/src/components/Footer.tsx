import Link from "next/link";
import { safeHref } from "@/lib/safe";
import { Logo } from "./Logo";

export function Footer({ brand, footer }: { brand: any; footer: any }) {
  return (
    <footer className="border-t border-line mt-28">
      <div className="wrap py-14 grid grid-cols-1 gap-10 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <Logo name={brand?.name} />
          <p className="muted mt-4 max-w-sm">{footer?.blurb}</p>
          {brand?.contact_email && <a className="link mt-4 inline-block" href={`mailto:${brand.contact_email}`}>{brand.contact_email}</a>}
        </div>
        {(footer?.columns || []).map((c: any) => (
          <div key={c.title}>
            <p className="font-semibold mb-3">{c.title}</p>
            <ul className="space-y-2">{(c.links || []).map((l: any) => <li key={l.href}><Link className="muted link" href={safeHref(l.href)}>{l.label}</Link></li>)}</ul>
          </div>
        ))}
      </div>
      <div className="wrap pb-10 muted text-sm flex flex-wrap gap-x-6 gap-y-2"><span>{footer?.legal}</span><Link className="link" href="/terms">Terms</Link><Link className="link" href="/privacy">Privacy</Link></div>
    </footer>
  );
}
