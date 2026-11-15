// Login. Players sign in with Google or Discord (whichever have keys in the environment);
// the session lives in a signed cookie, so login needs no database. Which player and thread a
// login belongs to comes from the emails `thread.py link` records.
import type { NextAuthOptions } from "next-auth";
import { getServerSession } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import DiscordProvider from "next-auth/providers/discord";
import GoogleProvider from "next-auth/providers/google";
import { threadForEmail } from "./store";
import { emailIsVerified } from "./verified.mjs";

const providers: NextAuthOptions["providers"] = [];
const env = process.env;

if (env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET) {
  providers.push(GoogleProvider({ clientId: env.GOOGLE_CLIENT_ID, clientSecret: env.GOOGLE_CLIENT_SECRET }));
}
if (env.DISCORD_CLIENT_ID && env.DISCORD_CLIENT_SECRET) {
  // Discord returns `iss=https://discord.com` with the code (RFC 9207); openid-client rejects the
  // callback unless the provider names that issuer.
  providers.push(
    DiscordProvider({ clientId: env.DISCORD_CLIENT_ID, clientSecret: env.DISCORD_CLIENT_SECRET, issuer: "https://discord.com" }),
  );
}

// Local testing only: sign in as any linked email without a password. Never in production.
export const devLogin = env.DEV_LOGIN === "1" && env.NODE_ENV !== "production";
if (devLogin) {
  providers.push(
    CredentialsProvider({
      id: "dev",
      name: "Local test login",
      credentials: { email: { label: "Linked email", type: "email" } },
      async authorize(credentials) {
        const email = credentials?.email?.trim().toLowerCase();
        return email && (await threadForEmail(email)) ? { id: email, email } : null;
      },
    }),
  );
}

export const authOptions: NextAuthOptions = {
  providers,
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  pages: { signIn: "/login" },
  callbacks: {
    // The email decides whose thread opens, so it must be one the provider verified.
    signIn: ({ account, profile }) => emailIsVerified(account?.provider, profile as Record<string, unknown> | undefined),
  },
};

/** The signed-in player's thread, or null (signed out, or no thread linked to this login). */
export async function currentThread() {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  const thread = await threadForEmail(email);
  return thread ? { ...thread, email: email as string } : null;
}
