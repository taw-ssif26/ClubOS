"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export type Me = { id: string; username: string; full_name: string; email: string; email_verified: boolean; is_platform_admin: boolean; totp_enabled: boolean; place?: string | null; place_name?: string | null; latitude?: number | null; longitude?: number | null; avatar_url?: string | null; bio: string; institution?: string | null; department?: string | null; class_year?: string | null; skills: string[]; profile_public: boolean; show_email: boolean } | null;
const Ctx = createContext<{ user: Me; loading: boolean; refresh: () => Promise<void>; logout: () => Promise<void> }>({ user: null, loading: true, refresh: async () => {}, logout: async () => {} });
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try { setUser(await api("/users/me")); } catch { setUser(null); } finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const logout = useCallback(async () => { try { await api("/auth/logout", { method: "POST" }); } finally { setUser(null); location.href = "/"; } }, []);
  return <Ctx.Provider value={{ user, loading, refresh, logout }}>{children}</Ctx.Provider>;
}
