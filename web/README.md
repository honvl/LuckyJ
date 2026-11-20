# Chat page

The web page where a player talks to their coach thread (see `../service/`). Next.js, deployed on
Vercel with the site.

- `app/chat`: the thread. History comes from the session's own event list; live events stream in
  over `/api/thread/stream`, and a dropped stream reconnects and refetches history, so a
  10-minute analysis survives a flaky connection. Nothing about the conversation is stored here.
- `app/(site)/start`: where a signed-in player waits for the chat: the subscribe form, the wait
  while their games are fetched (it asks again every minute), or a note that the login has no
  tutor. `/chat` forwards here. It sits under `app/(site)` because the chat page's own layout
  (Tailwind) does not load the site's stylesheet.
- `components/Markdown.tsx`: the coach's replies. Tables right-align numbers, grey the `± SE`,
  scroll sideways on a phone with the row label pinned, and copy as CSV. `[[5m]]` draws tiles
  with the guide's tile font. `[[game:<uuid> East 1-0 t9]]` shows a short label, and links to
  `replay.html` at that turn only once the game has a replay on the site.
- The bar in the header shows the share of this month's spending cap used, in percent.
- Chapters the coach packs (`chapter-<NN>-<slug>.tar.gz`) list with a Public/Private switch;
  public is the default.
- Login: Google or Discord, each enabled by its keys in the environment; sessions are signed
  cookies. `thread.py link <player> <email>` decides which thread a login opens, so only an email
  the provider has verified is accepted (`lib/verified.mjs`).

## Run locally

```bash
cd web && npm install
../.venv/bin/python ../service/thread.py link Honver honver@localhost
npm run dev   # http://localhost:3100
```

`web/.env.local` (not committed):

```
NEXTAUTH_URL=http://localhost:3100
NEXTAUTH_SECRET=<openssl rand -base64 32>
DEV_LOGIN=1                      # local only: sign in as a linked email, no password
SITE_URL=http://localhost:8765   # where replay.html is served (empty when the site is the same origin)
GOOGLE_CLIENT_ID=...            # optional, one pair per provider
GOOGLE_CLIENT_SECRET=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
```

The API key is read from `ANTHROPIC_API_KEY` or `service/.state/api_key`.

## Hosting

Live at https://ai.yui-life.com (luckyj.vercel.app forwards there; Vercel project `luckyj`, root directory `web`, team Honver
Lam's projects). Deploy from the repository root, so the build can copy `site/` in:

```bash
vercel deploy --prod
```

`.vercelignore` uploads only `site/` and `web/`. Player records are in the Neon Postgres database
`luckyj-db` (Vercel marketplace, free plan), whose address Vercel provides as `DATABASE_URL`;
`thread.py` reads the same address from `service/.state/database_url`. Production settings are
Vercel environment variables (`vercel env ls`): the API key, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`,
and the Google and Discord keys. The test login is off in production.

## Billing

Stripe Managed Payments (Stripe is merchant of record: tax, fraud, disputes, receipts from Link).
One product, tax code `txcd_10105001` (AI as a service, cloud, personal use), $20 a month plus tax.

- A login without a thread sees the sign-up form (Mahjong Soul or Tenhou, in-game name, publish
  by default) and goes to Stripe Checkout with `managed_payments.enabled`.
- `/api/billing/webhook` records the subscription (`subscriptions` table). On each renewal
  (`invoice.paid`, `subscription_cycle`) it sets the thread's cap to spent + `MONTHLY_ALLOWANCE_CENTS`
  (1500), so an unused month does not carry over. Messages need an active subscription
  (`active`, `trialing`, `past_due`) or a free player (`thread.py comp`).
- `thread.py pending` lists paying players still waiting; fetch their games, then
  `thread.py new <player> --games <dir> --email <email>` starts the thread with a $15 cap.
- Players cancel through Link or the customer portal (Manage subscription).
- `scripts/webhook-smoke.mjs` sends signed test events to a running page and checks the database.

Settings: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `MONTHLY_ALLOWANCE_CENTS`.

## Players, accounts and onboarding

- Sign-up asks for the Mahjong Soul server and in-game name; the player picks their account from
  the exact-name matches on that server (`/api/majsoul/lookup`; the server is `account_id >> 23`).
  The account id goes into `profiles`. Mahjong Soul only: Tenhou was dropped.
- `/account`: subscription (Stripe portal, using the tutor's own portal configuration), the
  Mahjong Soul account, the whole Personal Guide on/off (`players.book_public`), the default for
  new chapters, each chapter's switch, and closing the account.
- `thread.py onboard` fetches each waiting subscriber's games with `scripts/fetch_player_games.py`
  and starts their thread as player `ms-<account id>` once they have 10 ranked games. It runs on
  GitHub Actions (`.github/workflows/onboard.yml`): the Stripe webhook starts it after each
  purchase (`lib/onboard.ts`, env `GITHUB_DISPATCH_TOKEN`, a fine-grained token for this
  repository with "Actions: read and write"), and it also runs hourly for anyone still waiting.
  It logs in to Mahjong Soul as a separate fetch account, never the operator's playing account.
  Repository secrets: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `AMAE_KOROMO_TOKEN`,
  `MJS_ACCESS_TOKEN` (the fetch account's token), `MJS_RANDOM_KEY` (its device key). Mahjong
  Soul limits how many logs one account may retrieve (error 540, "log retrieval limit
  exceeded"), so more fetch accounts can be added as `MJS_ACCESS_TOKEN_2` .. `_8`, each with its
  own `MJS_RANDOM_KEY_<n>`: a run uses one account until it is over its limit, then the next,
  and its last line says how many logs each gave (about 20 an account, measured 20 Nov 2026).
  After onboarding the same run calls `thread.py games`, which tops up players who already have
  a thread toward their newest 100 games (40 a player a run at most): the new logs go up as one
  more archive (`/player/games-<n>.tar.gz`), it is mounted in the player's threads, and a note
  queued for their next message tells the tutor to unpack it. `state.players[...].games` records
  what each player has been given. Running the workflow with "check_login"
  ticked asks every account for one game and reports which can download. Variables:
  `MJS_BASE`, `MJS_GATEWAY`, `MJS_RES_VERSION` (bump on login error 151). Until the secrets
  exist the run does nothing. The repository is public, so the run prints no emails, names,
  account ids or game ids. thread.py's records (agent, environment, file ids, players) live in
  the database table `service_state`, shared by the cloud run and the operator's Mac.
- Going live with Stripe: `web/scripts/stripe-go-live.sh`, then enable the live webhook
  destination `luckyj-tutor-billing`.
- Terms of service: `site/terms.html`, `site/terms-ja.html`.

## Not done yet

Vercel Hobby does not allow commercial use: move to Pro before charging.
