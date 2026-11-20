// Starts the onboarding workflow (.github/workflows/onboard.yml) right after a purchase, so a new
// player's games are fetched and their thread started within minutes. The workflow also runs
// hourly, so a missing token or a failed call only delays a player; it never loses one.
//
// GITHUB_DISPATCH_TOKEN: a fine-grained token for this repository with "Actions: read and write".
export async function startOnboarding(): Promise<string> {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) return "onboarding waits for the hourly run (no GITHUB_DISPATCH_TOKEN)";
  const repo = process.env.ONBOARD_REPO || "honvl/LuckyJ";
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/onboard.yml/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    return res.ok ? "onboarding started" : `onboarding dispatch failed (${res.status})`;
  } catch (e) {
    return `onboarding dispatch failed (${(e as Error).message})`;
  }
}
