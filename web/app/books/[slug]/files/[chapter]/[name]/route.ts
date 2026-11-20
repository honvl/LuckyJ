// A figure from a public chapter of a player's book.
import { figure } from "@/lib/books";

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string; chapter: string; name: string }> }) {
  const { slug, chapter, name } = await params;
  const file = await figure(slug, decodeURIComponent(chapter), decodeURIComponent(name));
  if (!file) return new Response("not found", { status: 404 });
  return new Response(new Uint8Array(file.data), {
    headers: {
      "Content-Type": file.mime,
      "Cache-Control": "public, max-age=300",
      // An SVG figure is shown as an image only, never run as a page.
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
