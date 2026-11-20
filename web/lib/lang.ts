import "server-only";
import { cookies, headers } from "next/headers";
import type { Lang } from "./strings";

export { STRINGS, type Lang } from "./strings";

/** The reader's language: their pick from the site's language link (a cookie), else the browser's. */
export async function pageLang(): Promise<Lang> {
  const picked = (await cookies()).get("lang")?.value;
  if (picked === "ja" || picked === "en") return picked;
  const accept = (await headers()).get("accept-language") || "";
  return /^\s*ja\b/i.test(accept) ? "ja" : "en";
}
