-- Player records for the hosted chat page. Created by `thread.py db-sync`; safe to rerun.
create table if not exists players (
  name       text primary key,
  created_at timestamptz not null default now()
);

-- A login email opens its player's latest thread. Emails are stored lowercase.
create table if not exists logins (
  email  text primary key,
  player text not null references players(name) on delete cascade
);

-- intro: system context queued for the thread's next message, taken once.
create table if not exists threads (
  session_id text primary key,
  player     text not null references players(name) on delete cascade,
  created_at timestamptz not null default now(),
  intro      text
);

-- Chapters the player switched to private (public is the default).
create table if not exists private_chapters (
  player  text not null references players(name) on delete cascade,
  chapter text not null,
  primary key (player, chapter)
);

-- Players who use the tutor free (the site owner, testers). Everyone else needs a subscription.
alter table players add column if not exists comp boolean not null default false;

-- One row per subscribing login (Stripe Managed Payments). platform and game_name say whose
-- games to fetch; publish is the player's default for their chapters.
create table if not exists subscriptions (
  email              text primary key,
  customer_id        text,
  subscription_id    text unique,
  status             text not null,
  current_period_end timestamptz,
  platform           text,
  game_name          text,
  publish            boolean not null default true,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- Stripe events already handled (Stripe can deliver an event more than once).
create table if not exists billing_events (
  event_id    text primary key,
  type        text not null,
  received_at timestamptz not null default now()
);
