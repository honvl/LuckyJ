// The newest Personal Guides, for the shelf on the Playbook's home page (site/index.html and
// ja.html fetch this; ?lang=ja for Japanese titles). Public data only.
import { NextResponse } from "next/server";
import { libraryItems } from "@/lib/library";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const lang = new URL(request.url).searchParams.get("lang") === "ja" ? "ja" : "en";
  const items = (await libraryItems(lang)).slice(0, 3)
    .map(({ name, href, rank, chapters, latest }) => ({ name, href, rank, chapters, latest }));
  return NextResponse.json({ guides: items }, { headers: { "Cache-Control": "public, max-age=300" } });
}
