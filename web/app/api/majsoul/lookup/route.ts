// Exact-name Mahjong Soul accounts on one server, from amae-koromo's player search, so a player
// can pick themselves (the same nickname can exist on the China, Japan and International servers).
import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { SERVERS, exactMatches, rankName } from "@/lib/majsoul.mjs";

export async function GET(request: Request) {
  if (!(await getServerSession(authOptions))?.user?.email) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const url = new URL(request.url);
  const name = (url.searchParams.get("name") || "").trim().slice(0, 64);
  const server = url.searchParams.get("server") || "";
  const lang = url.searchParams.get("lang") === "ja" ? "ja" : "en";
  if (!name || !SERVERS.includes(server)) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const res = await fetch(`https://5-data.amae-koromo.com/api/v2/pl4/search_player/${encodeURIComponent(name)}?limit=50`, {
    headers: { "User-Agent": "LuckyJ AI Mahjong Tutor" },
    signal: AbortSignal.timeout(10_000),
  }).catch(() => null);
  if (!res?.ok) return NextResponse.json({ error: "lookup failed" }, { status: 502 });
  const matches = exactMatches(await res.json(), name, server).map((m) => ({
    id: m.id,
    nickname: m.nickname,
    rank: m.level ? rankName(m.level, lang) : "",
    latest: m.latest ? new Date(m.latest * 1000).toISOString().slice(0, 10) : null,
  }));
  return NextResponse.json({ matches });
}
