// A login's Mahjong Soul identity and publishing choice (table profiles). Needs the database.
import "server-only";
import { neon } from "@neondatabase/serverless";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;

export type Profile = {
  majsoulServer: string | null;
  majsoulName: string | null;
  majsoulAccountId: number | null;
  publish: boolean;
};

export async function getProfile(email: string): Promise<Profile | null> {
  if (!sql) return null;
  const [r] = await sql`select * from profiles where email = ${email.trim().toLowerCase()}`;
  return r
    ? { majsoulServer: r.majsoul_server, majsoulName: r.majsoul_name, majsoulAccountId: r.majsoul_account_id ? Number(r.majsoul_account_id) : null, publish: r.publish }
    : null;
}

export async function saveProfile(email: string, p: { majsoulServer: string; majsoulName: string; majsoulAccountId: number; publish?: boolean }) {
  if (!sql) throw new Error("no database");
  const who = email.trim().toLowerCase();
  await sql`
    insert into profiles (email, majsoul_server, majsoul_name, majsoul_account_id, publish)
    values (${who}, ${p.majsoulServer}, ${p.majsoulName}, ${p.majsoulAccountId}, ${p.publish ?? true})
    on conflict (email) do update set majsoul_server = excluded.majsoul_server, majsoul_name = excluded.majsoul_name,
      majsoul_account_id = excluded.majsoul_account_id, updated_at = now()`;
  if (p.publish !== undefined) await sql`update profiles set publish = ${p.publish} where email = ${who}`;
}
