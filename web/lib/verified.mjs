// A login opens a player's thread by its email, so the email must be one the provider has
// verified. Otherwise anyone could put a player's address on a new Discord account and sign in
// as them. Google sends `email_verified`, Discord sends `verified`.

/**
 * @param {string | undefined} provider
 * @param {Record<string, unknown> | undefined} profile
 */
export function emailIsVerified(provider, profile) {
  if (provider === "dev") return true; // local test login, never enabled in production
  if (!profile) return false;
  if (provider === "google") return profile.email_verified === true;
  if (provider === "discord") return profile.verified === true && typeof profile.email === "string";
  return false; // a provider without a known verified flag cannot open a thread
}
