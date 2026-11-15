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
