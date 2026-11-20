import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { thumbnail } from "@/lib/attachments";

/** An attached image's thumbnail (only the player's own). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await currentPlayer();
  if (!me) return new NextResponse(null, { status: 401 });
  const { id } = await params;
  const found = await thumbnail(me.player, id);
  const match = found?.thumb?.match(/^data:(image\/[\w+.-]+);base64,(.+)$/);
  if (!match) return new NextResponse(null, { status: 404 });
  return new NextResponse(Buffer.from(match[2], "base64"), {
    headers: { "Content-Type": match[1], "Cache-Control": "private, max-age=31536000, immutable" },
  });
}
