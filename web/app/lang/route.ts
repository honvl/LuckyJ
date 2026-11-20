// The header's language link: /lang?to=ja&back=/books remembers the pick for a year and goes back
// to the page. `back` must be a path on this site.
import { NextResponse } from "next/server";

export function GET(request: Request) {
  const url = new URL(request.url);
  const to = url.searchParams.get("to") === "ja" ? "ja" : "en";
  const back = url.searchParams.get("back") || "/books";
  const safe = back.startsWith("/") && !back.startsWith("//") ? back : "/books";
  const res = NextResponse.redirect(new URL(safe, url.origin));
  res.cookies.set("lang", to, { path: "/", maxAge: 365 * 24 * 3600, sameSite: "lax" });
  return res;
}
