# Chat page

The web page where a player talks to their coach thread (see `../service/`). Next.js, deployed on
Vercel with the site.

- `app/chat`: the thread. History comes from the session's own event list; live events stream in
  over `/api/thread/stream`, and a dropped stream reconnects and refetches history, so a
  10-minute analysis survives a flaky connection. Nothing about the conversation is stored here.
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

Live at https://luckyj.vercel.app (Vercel project `luckyj`, root directory `web`, team Honver
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

## Not done yet

Fetching a new player's games automatically (today: by hand, after `thread.py pending`). Chapter previews and
publishing to the site come after that. Vercel Hobby does not allow commercial use: move to Pro
before charging.
