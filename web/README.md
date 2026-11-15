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

## Not done yet

Player records live in `service/.state/` files, which a hosted deployment cannot write: they move
to a database with the billing step (Lemon Squeezy or Paddle), which also raises each thread's
cap once a month. Chapter previews and publishing to the site come after that.
