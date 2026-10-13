-- Per-visitor personal watchlists for the public Signal Screener site.
-- Run this once in your Supabase project's SQL Editor (Project -> SQL
-- Editor -> New query -> paste -> Run) after creating the project. See
-- .env.example for where SUPABASE_URL / SUPABASE_ANON_KEY come from.
--
-- This is entirely separate from the existing `companies` / `designations`
-- / `watchlist` tables in signal_screener.sql (your own CLI-managed
-- watchlist) — nothing here touches or depends on those.

create table if not exists public.user_watchlist (
  user_id uuid not null references auth.users(id) on delete cascade,
  entry_id text not null,
  entry_type text not null check (entry_type in ('designation', 'founder_stock')),
  added_at timestamptz not null default now(),
  primary key (user_id, entry_id)
);

-- Row Level Security: this is what actually makes it safe for every
-- visitor to share one public anon key. Without these policies enabled,
-- RLS defaults to denying everything; with them, a signed-in visitor can
-- only ever see or change their own rows — enforced by the database
-- itself, not by anything in the page's JavaScript.
alter table public.user_watchlist enable row level security;

create policy "select own watchlist rows"
  on public.user_watchlist for select
  to authenticated
  using (auth.uid() = user_id);

create policy "insert own watchlist rows"
  on public.user_watchlist for insert
  to authenticated
  with check (auth.uid() = user_id);

create policy "delete own watchlist rows"
  on public.user_watchlist for delete
  to authenticated
  using (auth.uid() = user_id);

-- Nothing else to run. Email magic-link sign-in is on by default for a new
-- Supabase project (Authentication -> Providers -> Email) — no further
-- configuration needed for that part.
