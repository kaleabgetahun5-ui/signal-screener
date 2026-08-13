"""Generates a static public HTML page from the current database, in the
same visual style as the earlier hand-built demos (signal-screener-v1.html,
nefl-screener-v1.html) — same fonts, colors, card layout, flag pills, and
verify-link rows, but driven by real pipeline data instead of hand-written
examples.

Two things the demos had that this page deliberately omits, because the
data doesn't exist yet:
  - The "$100 at IPO vs. S&P 500" backtest bars (nefl-screener-v1.html) —
    needs the `price_history` table, which isn't built (MVP roadmap step 6
    is the track-record checker; a backtest view isn't scheduled yet).
  - The "why this is worth a closer look" growth/analyst/bull-bear block
    (brief section 7) — needs real growth data, analyst targets, and news,
    none of which this pipeline pulls. Fabricating that content would
    violate the project's own guardrail against inventing facts not
    present in the input, so it's left out rather than faked.

What IS real and shown: for biotech entries, the company name as originally
submitted (not the resolved match, which can be wrong — see db.py's
raw_company_name note), the confidence flag, the Claude clinical summary,
and a verify link to the real ClinicalTrials.gov record. For founder-led
entries, the founder tier, the real ownership percentage and role sentence
pulled from the actual SEC filing, and a verify link straight to that
filing on sec.gov.
"""

import html
from datetime import date, timezone

from signal_screener import db

CONFIDENCE_CLASS = {
    "High signal": "high",
    "Moderate signal": "moderate",
    "Early stage": "early",
}
TIER_CLASS = {
    "Founder-CEO": "high",
    "Founder-Chair": "moderate",
    "Founder-departed": "early",
}
TIER_LABEL = {
    "Founder-CEO": "Founder-CEO tier",
    "Founder-Chair": "Founder-Chair tier",
    "Founder-departed": "Founder-departed",
}

CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

  :root{
    --bg:#EDF1F0; --card:#FFFFFF; --ink:#16233D; --ink-soft:#4A5568; --line:#D8DEDC;
    --high:#1F7A5C; --high-bg:#E5F3EC;
    --moderate:#B8862B; --moderate-bg:#FBF1DE;
    --early:#5B6B7A; --early-bg:#E9EDF0;
    --verify:#9C6B1F;
  }
  *{box-sizing:border-box;}
  body{margin:0; background:var(--bg); color:var(--ink); font-family:'IBM Plex Sans', sans-serif; padding:40px 20px 80px;}
  .wrap{max-width:780px; margin:0 auto;}
  header{margin-bottom:36px;}
  .eyebrow{font-family:'IBM Plex Mono', monospace; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-soft); margin-bottom:10px;}
  h1{font-family:'Source Serif 4', serif; font-weight:700; font-size:34px; margin:0 0 10px; letter-spacing:-0.01em;}
  h2.section-title{font-family:'Source Serif 4', serif; font-weight:600; font-size:22px; margin:44px 0 18px;}
  .sub{color:var(--ink-soft); font-size:15px; line-height:1.55; max-width:62ch;}

  .banner{background:var(--card); border:1px solid var(--line); border-left:4px solid var(--verify); border-radius:6px; padding:16px 18px; margin:24px 0 12px; font-size:14px; line-height:1.6; color:var(--ink-soft);}
  .banner b{color:var(--ink);}

  .card{background:var(--card); border:1px solid var(--line); border-radius:8px; margin-bottom:20px; overflow:hidden;}
  .card.with-tab{display:flex;}
  .tab{width:6px; flex-shrink:0;}
  .tab.high{background:var(--high);} .tab.moderate{background:var(--moderate);} .tab.early{background:var(--early);}
  .body{padding:20px 22px; flex:1; min-width:0;}
  .card-head{padding:20px 22px 0;}

  .top-row{display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; margin-bottom:6px;}
  .drug-name, .company-name{font-family:'Source Serif 4', serif; font-weight:600; font-size:19px;}
  .ticker{font-family:'IBM Plex Mono', monospace; font-size:12px; background:var(--bg); border:1px solid var(--line); border-radius:4px; padding:3px 8px; color:var(--ink-soft); white-space:nowrap;}
  .ticker.unverified{border-style:dashed; color:var(--verify);}

  .meta{font-size:13px; color:var(--ink-soft); margin-bottom:14px; line-height:1.6;}
  .meta strong{color:var(--ink); font-weight:500;}

  .flag{display:inline-block; font-family:'IBM Plex Mono', monospace; font-size:11px; letter-spacing:0.03em; text-transform:uppercase; padding:3px 9px; border-radius:20px; margin-bottom:12px;}
  .flag.high{background:var(--high-bg); color:var(--high);}
  .flag.moderate{background:var(--moderate-bg); color:var(--moderate);}
  .flag.early{background:var(--early-bg); color:var(--early);}

  .read{font-size:14.5px; line-height:1.65; color:var(--ink); margin-bottom:16px;}

  .verify-row{border-top:1px dashed var(--line); padding-top:12px; margin:0 22px 20px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;}
  .card.with-tab .verify-row{margin:0; padding:12px 22px; border-top:1px dashed var(--line);}
  .verify-label{font-family:'IBM Plex Mono', monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-soft); margin-right:2px;}
  .verify-row a{font-size:12.5px; color:var(--verify); text-decoration:none; border-bottom:1px solid transparent; padding:2px 0;}
  .verify-row a:hover, .verify-row a:focus-visible{border-bottom-color:var(--verify); outline:none;}
  .verify-row a:focus-visible{outline:2px solid var(--verify); outline-offset:2px; border-radius:2px;}
  .verify-note{font-size:12.5px; color:var(--verify); font-style:italic;}

  footer{margin-top:40px; font-size:12.5px; color:var(--ink-soft); line-height:1.75; border-top:1px solid var(--line); padding-top:18px;}
"""


def _flag_pill(label: str, css_class: str) -> str:
    return f'<div class="flag {css_class}">{html.escape(label)}</div>'


def _verify_note() -> str:
    return '<span class="verify-note">ticker not independently verified</span>'


def _render_biotech_card(row) -> str:
    verified = bool(row["ticker_verified"])
    ticker_class = "ticker" if verified else "ticker unverified"
    confidence = row["summary_confidence_flag"] or "Early stage"
    tab_class = CONFIDENCE_CLASS.get(confidence, "early")

    company = html.escape(row["raw_company_name"])
    drug = html.escape(row["drug_name"])
    ticker = html.escape(row["ticker"])
    designation_type = html.escape(row["type"])
    source = html.escape(row["source"])
    indication = html.escape(row["indication"] or "")
    read_text = html.escape(row["summary_text"] or "Summary not yet generated.")

    verify_links = []
    if row["trial_id"]:
        nct = html.escape(row["trial_id"])
        verify_links.append(
            f'<a href="https://clinicaltrials.gov/study/{nct}" target="_blank" '
            f'rel="noopener">ClinicalTrials.gov ({nct})</a>'
        )
    if verified:
        verify_links.append(
            f'<a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" '
            f'rel="noopener">Current price</a>'
        )
    verify_html = "".join(verify_links) if verify_links else ""
    if not verified:
        verify_html += _verify_note()

    return f"""
  <div class="card with-tab">
    <div class="tab {tab_class}"></div>
    <div class="body">
      <div class="top-row">
        <div class="drug-name">{drug} ({company})</div>
        <div class="{ticker_class}">{ticker}</div>
      </div>
      <div class="meta"><strong>{source} {designation_type}</strong> · granted {row['date_granted']} · {indication}</div>
      {_flag_pill(confidence, tab_class)}
      <div class="read">{read_text}</div>
      <div class="verify-row">
        <span class="verify-label">Verify:</span>
        {verify_html}
      </div>
    </div>
  </div>"""


def _render_founder_card(row, ownership) -> str:
    verified = bool(row["ticker_verified"])
    ticker_class = "ticker" if verified else "ticker unverified"
    tier = row["founder_tier"]
    tier_class = TIER_CLASS.get(tier, "early")
    tier_label = TIER_LABEL.get(tier, tier)

    name = html.escape(row["company_name"])
    ticker = html.escape(row["ticker"])
    exchange = html.escape(row["exchange"] or "")
    country = html.escape(row["country"] or "unknown")
    network_effect = html.escape(row["network_effect"] or "not identified in the source excerpt")

    if ownership:
        pct = (
            f"{ownership['ownership_pct']:.1f}%"
            if ownership["ownership_pct"] is not None
            else "not disclosed"
        )
        read_text = html.escape(ownership["role"])
        read_text += f" Ownership stake: {pct} (as of {ownership['as_of_date']})."
    else:
        read_text = "No ownership detail on file yet."

    verify_links = []
    if row["founder_tier_source"]:
        form, _, url = row["founder_tier_source"].partition(":")
        url = url or row["founder_tier_source"]
        if url.startswith("http"):
            verify_links.append(
                f'<a href="{html.escape(url)}" target="_blank" rel="noopener">'
                f"SEC {html.escape(form)} filing</a>"
            )
    if verified:
        verify_links.append(
            f'<a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" '
            f'rel="noopener">Current price</a>'
        )
    verify_html = "".join(verify_links) if verify_links else ""
    if not verified:
        verify_html += _verify_note()

    ticker_display = f"{exchange}: {ticker}" if exchange else ticker

    return f"""
  <div class="card">
    <div class="card-head">
      <div class="top-row">
        <div class="company-name">{name}</div>
        <div class="{ticker_class}">{ticker_display}</div>
      </div>
      {_flag_pill(tier_label, tier_class)}
      <div class="meta"><strong>HQ:</strong> {country} · <strong>Founder:</strong> {html.escape(row['founder_name'] or 'unknown')} · <strong>Network effect:</strong> {network_effect}</div>
      <div class="read">{read_text}</div>
    </div>
    <div class="verify-row">
      <span class="verify-label">Verify:</span>
      {verify_html}
    </div>
  </div>"""


def build_site_html() -> str:
    db.init_db()
    with db.connect() as conn:
        biotech_rows = conn.execute(
            """
            SELECT d.*, c.ticker_verified
            FROM designations d
            JOIN companies c ON c.ticker = d.ticker
            ORDER BY d.date_granted DESC, d.drug_name
            """
        ).fetchall()

        founder_rows = conn.execute(
            """
            SELECT * FROM companies
            WHERE listing_type = 'ADR'
            ORDER BY
                CASE founder_tier
                    WHEN 'Founder-CEO' THEN 0
                    WHEN 'Founder-Chair' THEN 1
                    WHEN 'Founder-departed' THEN 2
                    ELSE 3
                END,
                company_name
            """
        ).fetchall()

        founder_cards = []
        for row in founder_rows:
            ownership = conn.execute(
                "SELECT * FROM ownership WHERE ticker = ? "
                "ORDER BY as_of_date DESC, ownership_id DESC LIMIT 1",
                (row["ticker"],),
            ).fetchone()
            founder_cards.append(_render_founder_card(row, ownership))

    biotech_html = (
        "".join(_render_biotech_card(r) for r in biotech_rows)
        if biotech_rows
        else '<p class="sub">No biotech designations on file yet.</p>'
    )
    founder_html = (
        "".join(founder_cards)
        if founder_cards
        else '<p class="sub">No founder-led companies on file yet.</p>'
    )

    generated = date.today().isoformat()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Screener</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="eyebrow">Signal Screener · Live pipeline snapshot · {generated}</div>
    <h1>Biotech signals &amp; founder-led companies</h1>
    <div class="sub">FDA Breakthrough Therapy and EMA PRIME designations, plus a founder-led/network-effect stock screener, both pulled from real sources (SEC EDGAR, ClinicalTrials.gov, FDA/EMA) and summarized by Claude. Every card links to where the fact came from.</div>
  </header>

  <div class="banner">
    <b>How to validate this:</b> click "Verify" on each card — it goes straight to the source filing or trial record, not a paraphrase of one. Cards marked with a dashed, amber ticker failed independent verification (a second source didn't confirm the match) and are shown as-is rather than silently dropped or silently trusted. Nothing on this page is investment advice — confidence flags describe clinical/ownership facts, not buy or sell recommendations.
  </div>

  <h2 class="section-title">Biotech signals</h2>
  {biotech_html}

  <h2 class="section-title">Founder-led companies</h2>
  {founder_html}

  <footer>
    <b>Generated {generated}</b> from a live pipeline (not a live feed on this page — it's a static snapshot, rebuilt on demand). Ticker matching, verification, and classification methodology: <a href="https://github.com/kaleabgetahun5-ui/signal-screener" target="_blank" rel="noopener" style="color:var(--verify);">source on GitHub</a>. This omits the "why this is worth a closer look" growth/analyst/bull-bear section from earlier mockups — that needs a real growth-data and analyst-target source this pipeline doesn't pull yet, and this project doesn't fabricate that kind of content.
  </footer>

</div>
</body>
</html>
"""
