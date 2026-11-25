import type { NextRequest } from "next/server";
import { forward } from "@/lib/proxy";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path.map(encodeURIComponent).join("/"));
}
export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
