"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ children, admin }: { children: React.ReactNode; admin?: boolean }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const path = usePathname();
  useEffect(() => { if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(path)}`); }, [loading, user, router, path]);
  if (loading || !user) return <div className="wrap py-32 muted caret">Loading</div>;
  if (admin && user.is_platform_admin && !user.totp_enabled) return <div className="wrap py-32 max-w-2xl"><p className="display h-lg">Turn on two-factor authentication</p><p className="lede mt-3">The admin area controls site content, pricing and billing, so it requires a second factor. It takes a minute.</p><a className="btn btn-primary mt-8" href="/me?tab=security">Set it up</a></div>;
  if (admin && !user.is_platform_admin) return <div className="wrap py-32"><p className="display h-lg">Not available</p><p className="muted mt-2">This area is for platform administrators.</p></div>;
  return <>{children}</>;
}
