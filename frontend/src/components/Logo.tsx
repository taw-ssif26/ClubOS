export function Logo({ name = "ClubOS" }: { name?: string }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <path d="M3 8a2 2 0 012-2h22a2 2 0 012 2v4.2a3.8 3.8 0 000 7.6V24a2 2 0 01-2 2H5a2 2 0 01-2-2v-4.2a3.8 3.8 0 000-7.6z" fill="var(--accent)" />
        <path d="M20 8v3M20 14.5v3M20 21v3" stroke="var(--accent-fg)" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M9 13h6M9 17h4" stroke="var(--accent-fg)" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <span className="display text-[1.55rem] leading-none" style={{ letterSpacing: "-.03em" }}>{name}</span>
    </span>
  );
}
