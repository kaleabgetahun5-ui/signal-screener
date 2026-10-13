import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / os.environ.get("SIGNAL_SCREENER_DB_PATH", "data/signal_screener.db")
SEED_DATA_DIR = PROJECT_ROOT / "data"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("SIGNAL_SCREENER_CLAUDE_MODEL", "claude-sonnet-4-5")

CLINICALTRIALS_API_BASE = "https://clinicaltrials.gov/api/v2"

# SEC EDGAR requires a descriptive User-Agent (name + contact email) on every
# request or it returns 403/429. Set this to your own info via .env.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "signal-screener contact@example.com"
)

# Fallback ticker-matching source for companies not in SEC's US-filer list
# (matching/ticker_match.py) — mainly non-US EMA-designated companies. Free
# key, sign up at https://www.openfigi.com/user/signup. Works without a key
# too, just at a much lower rate limit (5 req/min search vs 20 req/min), so
# this is optional but recommended.
OPENFIGI_API_KEY = os.environ.get("OPENFIGI_API_KEY")

# Tier 2 (brief section 3), South Korea: filings/korea.py uses this for
# DART's executive-status and major-shareholding endpoints. Free key,
# sign up at https://opendart.fss.or.kr (Korean site; the key request form
# is under "인증키 신청/관리" after registering). Required for any Tier 2
# Korean candidate — unlike OpenFIGI, DART has no unauthenticated fallback.
OPENDART_API_KEY = os.environ.get("OPENDART_API_KEY")

ALLOWED_CONFIDENCE_FLAGS = ("High signal", "Moderate signal", "Early stage")

# Per-visitor personal watchlists on the public site (distinct from the
# single owner-curated "Your watchlist" section, which stays exactly as it
# was — CLI-only, baked in at generate-site time). This is the only part of
# the site that isn't a static snapshot: the generated page embeds these two
# values directly (SUPABASE_ANON_KEY is a public, publishable key by
# Supabase's own design — safe to ship in client-side HTML, unlike a
# service-role key, which must never appear here) and the page's own
# JavaScript talks to Supabase directly from each visitor's browser. Both
# unset simply means the personal-watchlist UI doesn't render at all (see
# site.py's SUPABASE_CONFIGURED) — the rest of the site is unaffected.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# Weekly email digest (MVP roadmap step 4). SMTP rather than a provider API
# so the pipeline stays self-contained and can run unattended from a
# scheduled job, not just from within an authenticated chat session.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
DIGEST_FROM_EMAIL = os.environ.get("DIGEST_FROM_EMAIL") or SMTP_USERNAME
DIGEST_TO_EMAIL = os.environ.get("DIGEST_TO_EMAIL")
