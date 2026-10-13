# Setting up per-friend personal watchlists

The code is built and tested (174/174 passing, including new tests for this feature) — this doc is just the remaining steps that have to happen in your own browser, which I can't do for you.

## 1. Create a free Supabase project

Go to [supabase.com](https://supabase.com), sign up (free tier), and create a new project. Pick any name/region/password — the password here is just Supabase's own database password, not something visitors ever see or use.

## 2. Run the schema

In your new project, go to **SQL Editor** (left sidebar) → **New query**, paste in the contents of `supabase_watchlist_schema.sql` (in the repo root, sent alongside this doc), and click **Run**. That creates the one new table (`user_watchlist`) and the three security policies that keep each visitor's list private to them.

Email sign-in is on by default for a new project — nothing else to configure there.

## 3. Get your project's URL and key

Still in Supabase: **Project Settings** (gear icon) → **API**. Copy two values:
- **Project URL** (looks like `https://xxxxxxxx.supabase.co`)
- **anon / public key** (a long string starting with `eyJ...`) — this one is *meant* to be public, it's safe to use in client-side code. Don't copy the `service_role` key instead — that one must stay private, and this feature never needs it.

## 4. Add them as GitHub secrets

So the daily pipeline can bake them into the generated site: on GitHub, go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**, and add two:
- `SUPABASE_URL` = the Project URL from step 3
- `SUPABASE_ANON_KEY` = the anon key from step 3

## 5. Get it live

Either wait for tomorrow's scheduled run, or trigger it now yourself: **Actions** tab → **Daily pipeline** → **Run workflow**. Once it finishes, your site will have the new "☆ My personal watchlist" section with a sign-in box.

## 6. Test it

Visit your live site, enter your own email in the sign-in box, check your inbox for the magic link, click it, and confirm you land back on the site signed in. Click "+ My watchlist" on a couple of cards, refresh the page, sign in again, and confirm they're still there. That's the whole loop working.

## If you also want to test locally first

Add the same two values to your local `.env` file (see `.env.example`), then run `signal-screener generate-site -v` and open the resulting `docs/index.html` file directly in a browser before pushing anything.

## What this doesn't affect

Your own "★ Your watchlist" section (the one with BE in it right now) is completely separate and untouched — it still works exactly as it did, via `signal-screener watchlist-add` on your machine. This new section is purely additive, for visitors who want their own private list.
