import type { NextRequest } from "next/server";
import { forward } from "@/lib/proxy";

/** Uploaded images and documents. Goes through the retrying proxy so a sleeping free-tier API doesn't produce broken images.
 *  The API marks files immutable, so Vercel's CDN caches them for a year after the first successful fetch. */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, `media/${path.map(encodeURIComponent).join("/")}`);
}
