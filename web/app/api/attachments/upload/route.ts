import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { planFor } from "@/lib/attachments";
import { accessFor } from "@/lib/billing";
import { newKey, r2Enabled, uploadUrl } from "@/lib/r2";

/** A signed URL the browser can PUT one file to (R2), for files of any size up to the limit. */
export async function POST(request: Request) {
  if (!r2Enabled) return NextResponse.json({ error: "direct uploads are off" }, { status: 501 });
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!(await accessFor(me.email)).allowed) return NextResponse.json({ error: "subscription" }, { status: 402 });
  const body = await request.json().catch(() => ({}));
  const name = String(body?.name || "file").slice(0, 200);
  const plan = planFor(name, String(body?.type || ""), Number(body?.size) || 0, true);
  if ("error" in plan) return NextResponse.json({ error: plan.error }, { status: 400 });
  const key = newKey(me.player, name);
  return NextResponse.json({ key, url: await uploadUrl(key) });
}
