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

-- One Mahjong Soul name and one Tenhou name per player (at least one). platform and game_name
-- above are from the first sign-up form and kept for old rows.
alter table subscriptions add column if not exists majsoul_name text;
alter table subscriptions add column if not exists tenhou_name text;

-- Player books (luckyj.vercel.app/books/<slug>). book_name is what the book is published under
-- (the Mahjong Soul name, else the Tenhou name, else the player's name); synced_at throttles the
-- check for new chapter archives.
alter table players add column if not exists book_name text;
alter table players add column if not exists slug text unique;
alter table players add column if not exists synced_at timestamptz;

-- One row per chapter the coach packed (chapter-<NN>-<slug>.tar.gz). key is "<NN>-<slug>".
-- A newer archive of the same chapter replaces it (source_file_id tells them apart).
create table if not exists chapters (
  player         text not null references players(name) on delete cascade,
  key            text not null,
  number         int  not null,
  title          text not null,
  markdown       text not null,
  spots          jsonb,
  source_file_id text not null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  primary key (player, key)
);

-- Figures shipped with a chapter, stored as base64 (small images only).
create table if not exists chapter_files (
  player  text not null,
  key     text not null,
  name    text not null,
  mime    text not null,
  data    text not null,
  primary key (player, key, name),
  foreign key (player, key) references chapters(player, key) on delete cascade
);
