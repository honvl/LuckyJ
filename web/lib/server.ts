// Server-only helpers: the API client and where the operator's local files live.
import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const REPO = resolve(process.env.REPO_ROOT || join(process.cwd(), ".."));
export const STATE_DIR = join(REPO, "service", ".state");
export const MA_BETA = "managed-agents-2026-04-01";

let client: Anthropic | null = null;

export function anthropic(): Anthropic {
  if (client) return client;
  let key = process.env.ANTHROPIC_API_KEY?.trim();
  const keyFile = join(STATE_DIR, "api_key");
  if (!key && existsSync(keyFile)) key = readFileSync(keyFile, "utf8").trim();
  if (!key) throw new Error("No API key: set ANTHROPIC_API_KEY or put it in service/.state/api_key");
  client = new Anthropic({ apiKey: key });
  return client;
}
