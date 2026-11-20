// A thread whose conversation grew too long goes on in a fresh session (rules and reasons in
// rollover-rules.mjs). Checked when the player sends a message; the old session keeps its
// history, which the chat page still shows above the new one.
import "server-only";
import { neon } from "@neondatabase/serverless";
import { ownChapters } from "./books";
import { carryOverText, contextTokens, ROLLOVER_TOKENS, shouldRollOver, transcriptTail } from "./rollover-rules.mjs";
import { anthropic } from "./server";
import { createThread, heroNames, introFor } from "./threads";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;
const LIMIT = Number(process.env.ROLLOVER_TOKENS || ROLLOVER_TOKENS);

/** The size of the session's conversation, from its newest model request. */
async function sessionTokens(sessionId: string): Promise<number> {
  const page: any = await anthropic().beta.sessions.events.list(sessionId, {
    order: "desc", types: ["span.model_request_end"], limit: 1,
  } as any);
  const ev = page?.data?.[0];
  return contextTokens(ev?.model_usage);
}

async function titleOf(player: string, sessionId: string): Promise<string | null> {
  if (!sql) return null;
  const [r] = await sql`select title from threads where session_id = ${sessionId} and player = ${player}`;
  return r?.title ?? null;
}

/** The session the player's message should go to: `sessionId`, or a fresh one that carries it on
 * when it has grown past the limit. */
export async function sessionForMessage(player: string, sessionId: string): Promise<string> {
  const session: any = await anthropic().beta.sessions.retrieve(sessionId);
  const tokens = await sessionTokens(sessionId);
  if (!shouldRollOver(tokens, session.status, LIMIT)) return sessionId;

  const events: any[] = [];
  for await (const ev of anthropic().beta.sessions.events.list(sessionId, {
    types: ["user.message", "agent.message"], limit: 1000,
  } as any)) events.push(ev);
  const { chapters } = await ownChapters(player);
  const intro = carryOverText({
    intro: introFor(player, await heroNames(player)),
    chapters: chapters.map((c: any) => ({ number: c.number, title: c.title })),
    tail: transcriptTail(events),
  });
  const next = await createThread(player, { continues: sessionId, intro, title: await titleOf(player, sessionId) });
  console.log(`thread rolled over at ${tokens} tokens`);
  return next;
}
