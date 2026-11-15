import "server-only";
import { headers } from "next/headers";
import type { Lang } from "./strings";

export { STRINGS, type Lang } from "./strings";

export async function pageLang(): Promise<Lang> {
  const accept = (await headers()).get("accept-language") || "";
  return /^\s*ja\b/i.test(accept) ? "ja" : "en";
}
