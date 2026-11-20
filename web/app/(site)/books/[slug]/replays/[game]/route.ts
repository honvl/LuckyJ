// A replay of a game a public chapter cites (lib/books.ts bookReplay), for
// site/replay.html?b=<slug>&g=<game>. The viewer asks for "<game>.json".
import { bookReplay } from "@/lib/books";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string; game: string }> }) {
  const { slug, game } = await params;
  const id = game.replace(/\.json$/, "");
  if (!/^[a-z0-9-]{2,60}$/.test(slug) || !/^\d{6}-[0-9a-f-]{8,40}$/.test(id)) return new Response("not found", { status: 404 });
  const json = await bookReplay(slug, id);
  if (!json) return new Response("not found", { status: 404 });
  return new Response(json, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=300" } });
}
