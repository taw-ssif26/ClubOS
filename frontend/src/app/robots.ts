import type { MetadataRoute } from "next";
import { SITE } from "@/lib/server";

export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", allow: "/", disallow: ["/api/", "/manage/", "/admin", "/me", "/upgrade", "/new-club", "/login", "/register"] }], sitemap: `${SITE}/sitemap.xml` };
}
