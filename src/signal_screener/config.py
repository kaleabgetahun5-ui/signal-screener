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

ALLOWED_CONFIDENCE_FLAGS = ("High signal", "Moderate signal", "Early stage")

# Weekly email digest (MVP roadmap step 4). SMTP rather than a provider API
# so the pipeline stays self-contained and can run unattended from a
# scheduled job, not just from within an authenticated chat session.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
DIGEST_FROM_EMAIL = os.environ.get("DIGEST_FROM_EMAIL") or SMTP_USERNAME
DIGEST_TO_EMAIL = os.environ.get("DIGEST_TO_EMAIL")
