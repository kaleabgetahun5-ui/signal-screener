# Project Brief: Signal Screener
*A physician-curated screener for high-potential biotech/medtech companies + a global founder-led/network-effect stock screener*

## 1. Concept

Two related screening tools, built on the same underlying pipeline pattern (pull public data → apply a quality filter → summarize with AI → backtest → distribute):

**A. Biotech/Medtech Signal Screener**
Surfaces early-stage pharma/medtech companies with strong clinical signals (breakthrough designations, positive trial results) before the broader market notices — using a physician's clinical judgment (yours) baked into the AI summarization layer as the differentiator.

**B. Global Founder-Led + Network-Effect Screener**
Modeled on Chris Koerner's NEFL Stocks (neflstocks.com) — screens for companies that are (1) still run by their founder and (2) benefit from network effects, then backtests performance since IPO. Extended beyond the US/S&P 500 to include international companies.

---

## 2. Data Schema

**`companies`**
```
ticker, company_name, exchange, country, market_cap, currency, sector, 
founder_tier ("Founder-CEO" | "Founder-Chair" | "Founder-departed" | "N/A"), 
listing_type ("primary" | "ADR")
```

**`designations`** (biotech signal table)
```
designation_id, company_id, source ("FDA" | "EMA"), 
type ("Breakthrough Therapy" | "Fast Track" | "PRIME" | "Orphan Drug"),
date_granted, drug_name, indication, trial_id
```

**`trials`**
```
trial_id, registry ("ClinicalTrials.gov" | "EU CTIS"), 
phase, status, start_date, primary_completion_date, condition
```

**`ownership`** (for the founder-led screener)
```
company_id, founder_name, role, ownership_pct, source ("SEC Form 4" | "20-F" | "annual report"), as_of_date
```

**`price_history`**
```
ticker, date, close_price_local, close_price_usd, index_benchmark
```

**`tracked_outcomes`** (the track-record table — the single most important addition)
```
entry_id, entry_type ("designation" | "founder_stock"), date_flagged, 
flag_given ("High signal" | "Moderate signal" | "Early stage" etc.),
price_at_flag, price_at_3mo, price_at_6mo, price_at_12mo, 
notes_on_outcome
```

**`user_notes`**
```
note_id, entry_id, date_written, note_text
```

---

## 3. Data Sources

### Biotech/Medtech Screener
- **FDA Breakthrough Therapy / Fast Track lists** — public, updated periodically
- **ClinicalTrials.gov API** — trial phase/status, free, no key required
- **EMA PRIME designations** — EU's fast-track equivalent, public
- **EU CTIS (Clinical Trials Register)** — EU trial data
- **WHO ICTRP** — meta-registry aggregating US/EU/Japan/China/India trial registries; worth using as a first pass before building per-country integrations

### Founder-Led + Network-Effect Screener
- **Tier 1 (start here): Foreign companies listed as ADRs on NYSE/NASDAQ** — MercadoLibre, Sea Limited, PDD Holdings, Coupang, Grab. **Correction based on the actual build:** not all of these file as foreign private issuers. MercadoLibre and Coupang are Delaware-incorporated U.S. domestic filers, using the same 10-K/DEF 14A filings as any American company — only some Tier 1 companies (like Sea Limited, PDD, Grab) file the foreign-issuer forms (20-F/6-K) originally assumed here. The pipeline should check both filing types per company and prefer DEF 14A when available, since it has a cleaner ownership table than 20-F.
- **Tier 2 (later): Companies listed only on foreign exchanges** — Adyen, Zalando, Naver, Tencent. Needs country-specific sources: Companies House + LSE (UK), Bundesanzeiger (Germany), HKEX disclosure of interests (Hong Kong), DART (South Korea). Founder-ownership data is harder to source cleanly here — expect to lean on Claude to extract stakes from annual report PDFs.
- **Market data (both tiers)**: EOD Historical Data or Alpha Vantage — covers 60+ global exchanges, normalize to USD for consistent backtesting.

---

## 4. Pipeline (runs daily/weekly)

1. Pull new designations (FDA + EMA) and new ADR filings (SEC EDGAR)
2. Match drugs/companies to public tickers (fuzzy matching — expect manual curation early on)
3. **Verify every matched ticker before it's used anywhere downstream** — this step is mandatory, not optional, and must run for every entry every time, not just when something looks uncertain. Cross-check the matched ticker against a second independent source (e.g. the exchange's own listing page or a market-data API) before accepting it. If verification fails or is ambiguous, the entry is flagged "unverified" and shown as such — it is never silently dropped or silently trusted.
4. **Re-verify status facts that can change over time, not just at match time** — this applies especially to "founder-led" status (a founder can step back from CEO, as MercadoLibre's Marcos Galperin did in Jan 2026) and company listing status (tickers can delist, get acquired, or move exchanges). Re-run this check on every scheduled pipeline run, not once at initial entry.

   **Founder-led classification rule (applied consistently, not case-by-case):** use three objective tiers rather than a single yes/no, so a founder stepping back from CEO doesn't silently drop a company from the screener or silently get waved through — it gets classified transparently instead.
   - **Founder-CEO** — founder currently holds the CEO title.
   - **Founder-Chair** — founder stepped back from CEO within the last 24 months, but still holds Chairman/Executive Chairman AND retains a meaningful ownership stake (>5%, adjustable). Shown in the main list, tagged distinctly — not hidden, not silently merged with Founder-CEO.
   - **Founder-departed** — founder holds no active leadership role, or the transition happened more than 24 months ago. Removed from the main list, but kept in a separate "alumni" reference so it's clear why, rather than just disappearing.
   
   Both the title and ownership-percentage checks must be pulled from actual filings (Form 4/8-K/20-F, or annual report equivalents abroad) — never inferred or guessed.
5. Pull trial detail (ClinicalTrials.gov / EU CTIS) and ownership detail (Form 4 / 20-F)
6. Generate plain-English summaries via Claude (see prompts below)
7. Store results, run backtests once enough historical data accumulates — every backtest figure should store its as-of date and source, since prices and index levels are only accurate at the moment they were pulled

---

## 5. Claude Prompts

**Biotech signal summarization:**
```
You are helping a physician-run investment research tool summarize 
clinical significance for a general audience.

Given this data:
- Drug: {drug_name}
- Company: {company_name} ({ticker})
- Designation: {designation_type} granted {date}
- Indication: {indication}
- Trial phase: {phase}, Status: {status}
- Mechanism (if known): {mechanism}

Write:
1. A 2-sentence plain-English explanation of what this drug does 
   and why the designation matters clinically (not just "it's promising")
2. One sentence on how differentiated this is vs. existing treatments 
   for the same condition, if known
3. A confidence flag: "High signal" / "Moderate signal" / "Early stage" 
   based on trial phase and designation strength alone — 
   NOT a buy/sell recommendation

Do not speculate about stock price movement. Stick to clinical facts.
```

**Founder-led/network-effect extraction (for annual reports where structured data isn't available):**
```
Given this excerpt from {company_name}'s annual report or 20-F filing, extract:
1. Is the original founder still in an active leadership role (CEO, Chair, or 
   equivalent)? State their current title.
2. Approximate founder ownership stake, if disclosed.
3. Based on #1 and #2, classify into exactly one tier: "Founder-CEO" 
   (founder is current CEO), "Founder-Chair" (founder stepped back from 
   CEO but holds Chairman/Executive Chairman AND >5% ownership), or 
   "Founder-departed" (neither of the above applies). If the transition 
   date isn't in this excerpt, say so explicitly rather than guessing 
   how recent it was.
4. One sentence describing the company's core network effect, if one exists 
   (e.g., more users → more value for each user), or "None identified" if 
   the business model doesn't have one. Unlike items 1-3, this question is 
   about the company's general business model, not something the leadership/
   ownership excerpt itself will describe — answer it from general knowledge 
   of the company, not from the excerpt. (This distinction matters: an 
   earlier build of this prompt scoped item 4 to excerpt-only too, and it 
   silently returned "None identified" for genuinely network-effect 
   businesses like Sea Limited and Grab, simply because leadership/ownership 
   sections never discuss business model.)

Source text:
{report_excerpt}
```

**Stock context / "why this is worth a closer look" summarization (used for BOTH screeners — every public company gets this, not just the NEFL screener):**
```
You are helping a personal research tool summarize why a company is worth 
a closer look — not whether to buy or sell it.

Given this data:
- Company: {company_name} ({ticker})
- Recent revenue/growth figures: {growth_data}
- Recent news driving the stock: {recent_news}
- Current analyst price targets: {analyst_targets} (list of firm + target)

Write:
1. One sentence stating the growth trend using the real numbers given — 
   no forecasting beyond what's provided
2. One sentence on what's currently driving the stock, in plain terms
3. The analyst target range exactly as given (low–high, count of analysts), 
   labeled clearly as analysts' opinions, not yours
4. A short bull case (2-3 sentences) and a short bear case (2-3 sentences), 
   both grounded only in the data given — do not invent facts not present 
   in the input

Do not generate a price projection of your own, at any time horizon. 
Do not state or imply whether this is a good investment — describe the 
debate, don't resolve it.
```

---

## 6. Guardrails
- All AI output should stay in the lane of "clinical fact" or "company/ownership fact" — never a buy/sell recommendation. This keeps the tool as a research aid rather than investment advice, which matters both practically (trust) and regulatorily (avoiding investment-adviser registration issues).
- Track and disclose data source + as-of date for every data point — this is a credibility-critical feature for any screener product.
- **Confidence flags must be exactly one of the three defined labels — "High signal" / "Moderate signal" / "Early stage" — never a hybrid or a custom label (e.g. not "Moderate–high signal" or "Early stage — high-risk microcap").** Extra context belongs in the written summary text, not folded into the flag itself. This matters for a real reason, not just tidiness: the app needs to filter/sort by flag later, and a flag field with inconsistent values silently breaks that.

---

## 7. "Why this is worth a closer look" section (per company — both screeners)

Every company entry, in **both** the biotech screener and the NEFL screener, gets this section — a public biotech company's stock behaves like any other stock, so the same stock-context treatment applies regardless of which screener surfaced it. This is separate from and additional to the clinical summary (biotech) — the two stay in clearly labeled, separate parts of the entry, never merged into one paragraph.

Every company entry should explain *why it surfaced as a candidate* — without slipping into "you should invest" territory. The distinction: describe the business and the debate around it; never hand down a conclusion.

Include:
- **Growth trend** — real historical data (e.g. revenue growth over the last 4-8 quarters), not a forecast
- **What's currently driving the stock** — in plain terms, e.g. "margin pressure from shipping investment" or "fintech arm scaling fast"
- **Analyst price target range** — the actual current spread of Wall Street targets (low/high, number of analysts), clearly labeled as *their* opinions, not the tool's
- **Bull case vs. bear case** — a short, evenhanded summary of what optimists and skeptics are each saying about the stock right now, sourced from real commentary, not invented

Explicitly excluded:
- **No price projections** — 3/6/12-month or 5/10-year forecasts are not included. Nobody can reliably predict these, and generating a number creates false precision that looks like information but isn't. Historical trend data is a substitute for this, not projections dressed up as data.
- **No "good investment" framing** — the tool explains why a company is a *candidate worth a closer look* (interesting growth, notable designation, real network effect), not whether the person should buy it. Showing bull/bear disagreement openly is more honest and more useful than a single confident-sounding conclusion.

---

## 8. Features that make this worth using long-term

These aren't nice-to-haves — they're the difference between a tool that gets checked once and abandoned, and one that's still useful a year from now.

- **"What's new since last time" view** — the primary way you interact with the tool day-to-day should be a diff, not a full re-read. Show only what changed or was newly added since your last visit.
- **Automatic track record (uses the `tracked_outcomes` table above)** — every time something gets flagged "High signal," the pipeline checks back automatically at 3/6/12 months and records what actually happened to the price. This is the most important feature in the whole project: it's the only thing that tells you, honestly, whether the screening logic is any good — without it, you're just accumulating opinions with no feedback loop.
- **Personal notes field per entry (`user_notes` table)** — a place for your own read on each company/drug, especially on the biotech side where your clinical judgment is the actual differentiator. Your own past notes will be more valuable to future-you than anything the AI generates.
- **Weekly digest, not real-time alerts** — real-time feels powerful but mostly just creates noise and encourages reacting to short-term movement instead of signal.
- **Source + as-of date on everything** — already specified above; non-negotiable.

## 9. Deliberately excluded — not just "later," actually out of scope

Written down explicitly so these don't quietly creep back in as "obvious" additions down the line.

- **Any numeric confidence score (e.g. "82/100").** Same problem as price projections — false precision that looks like data but isn't, and it starts doing the thinking for you. Keep plain-language flags (High/Moderate/Early) — they're honest about their own fuzziness.
- **Real-time price tickers or a live dashboard.** Adds cost (paid data APIs), adds maintenance burden, and encourages checking too often, which hurts decision quality rather than helping it.
- **Any trade execution or brokerage connection.** This tool never moves money or places trades on its own. It stays strictly a research aid. This is the firmest line in the whole project — the moment it can act on your behalf, the risk profile changes completely.
- **Multi-user accounts, logins, or payments.** This is a personal-use tool. Building any of this now is wasted effort for a "maybe later."
- **Push notifications / SMS alerts.** Sounds convenient, becomes noise. The weekly digest is enough — checking in stays your choice, not the tool's.

---

## 10. MVP Roadmap
1. Build biotech pipeline for FDA data only (US) — smallest possible working version
2. Add EMA data once step 1 works end to end
3. Add founder-led/network-effect Tier 1 (ADR) companies using the same SEC EDGAR connection
4. Ship as a weekly email digest before building any dashboard UI
5. Add the "what's new since last time" diff view and the notes field — these are cheap to build and make the tool usable day-to-day
6. Add the automatic track-record checker (3/6/12-month follow-up) once you have your first batch of flagged entries to actually track
7. Add Tier 2 international companies once there's validated demand
