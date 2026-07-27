# Build Log

Per-session record of work: what the AI produced, and what I (nageen24) changed, corrected, or decided on top of it. Feeds the final Build Session Summary. Honest hours only.

---

## Session 1 — 2026-07-27 — Planning & design

**Duration:** ~ (planning session)

**What happened:** Worked through the assessment requirements and locked the design before writing any code.

**AI produced:** requirement breakdown, candidate source lists, schema draft, stack options, spec document draft.

**What I decided / changed on top of it:**
- Rejected the AI's initial hosting plan (Vercel + local embedding model). Chose Gemini free embedding API (memory-safe on free tier) and consolidated everything on Render for a clean, single-platform deploy.
- Pressure-tested the discovery source list myself and added 3 more (job postings, conferences/podcasts, OpenCorporates) to widen hidden-SFO discovery and guard against single-source bias.
- Chose two-source verification (free-tier tool + independent free cross-check) per high-value cell.
- Chose agentic 2-LLM validation (Andrew Ng reflection pattern) as the grounding control, layered with a retrieval gate.
- Committed to standout additions: rejection log, adversarial RAG test set, dataset self-scorecard, written SFO proof-standard.
- Caught flaws in the assessment's own framing (SFO-vs-contact contradiction, privacy silence, fuzzy manual/pipeline line, SEC-exemption blind spot, Task 2 bait framing).

**Decisions log:** see `DECISIONS.md`. **Spec:** see `docs/superpowers/specs/2026-07-27-family-office-rag-design.md`.

**Next session:** build the dataset pipeline first (discovery → enrichment → validation).

---

## Session 2 — 2026-07-27 — Dataset pipeline build

**What the AI produced:** the full pipeline scaffold and code — shared schema, 5 discovery modules, enrichment scraper, validation engine, orchestrator, PROOF_STANDARD.md. For the ToS-restricted sources (LinkedIn, job boards, conferences) the AI proposed keeping them as a "manual-leads" channel (a CSV I'd fill by hand that then flows through the pipeline).

**What I decided / changed on top of it:**
- **Rejected the manual-leads workaround.** The assessment forbids manual compilation of records, and I don't want any fake or hand-assembled entries padding the file just to claim more sources. I told the AI to remove those sources entirely and document why, rather than fake coverage.
- Chose to stand on **4 genuinely automated, diverse sources** (SEC EDGAR, ProPublica 990, Google News, OpenCorporates) and, if they don't yield 50, to widen queries within them before ever adding a fake or manual source.
- Reasoning captured in DECISIONS.md; honesty of the dataset takes priority over source count.

**Next:** run the pipeline (discovery first, no keys needed) and see the real candidate yield before enrichment.

---

## Session 3 — 2026-07-27 — First discovery run + noise strategy

**What the AI produced:** installed the Python deps, ran the discovery stage (no API keys), and reported the real yield honestly — 120 unique candidates (SEC 40, ProPublica 990 40, Google News 40, OpenCorporates 0/401). It then read the actual candidate names back to me and flagged the quality problems itself (SEC noise, generic charities, a broken news-name extractor) instead of just reporting the count. It laid out three cleanup strategies with tradeoffs and recommended option 1.

**What I decided / changed on top of it:**
- **Chose Option 1** (wide net + strict validation as the filter + rejection log as proof), and had it logged as my decision with my own reasoning — see DECISIONS.md. Core of my reasoning: the assessment rewards validation that *changes* the output, so I want junk to flow in and be visibly rejected; and hard front-door filtering would kill the hidden SFOs this task values most.
- Treated the broken Google News extractor as a plain bug to fix regardless of strategy.
- Held the line on: no fake, no manual compilation — close the gap to 50 by widening honest queries, or ship fewer real records and say so.

**Next:** fix the news extractor, widen SEC/990 queries + raise caps for more real throughput, re-run discovery, then move to enrichment.

**Executed (same session):**
- Fixed the Google News extractor (made it a pure, unit-tested `extract_firm_name`): restricted to names ending in "Family Office" + a stopword filter for headline words/verbs. News precision went from ~10% to ~55%; real named FOs now surface (Perot, Pritzker, Dalio, Goldman, Raffles, Callan, UBS, INVL, Ayco).
- Widened SEC (3 phrasings + pagination) and ProPublica 990 (5 queries + pagination) for more real throughput per my wide-net decision.
- Re-ran discovery at cap 80/source: **233 unique candidates** (SEC 80, 990 80, News 73, OpenCorporates 0/401). Up from 120. Genuine FO signal now comfortably above the 50 target *before* validation attrition — the point of option 1.
- Left the residual news fragments in on purpose: they're what validation + the rejection log are for.

**Next:** enrichment (AUM/thesis/contacts + dated signals), then Rule-2 validation → dataset.csv + rejection_log.csv + scorecard.

## Session 4 — 2026-07-27 — Principal/signal enrichment + Google→Wikidata pivot

**What the AI produced:** per-firm news enrichment (recent dated signal + principal name from headlines), SEC-filing enrichment (official business phone/address), AUM + mandate extractors, and a Wikidata website resolver.

**What I decided / changed on top of it:**
- Re-read the assessment and caught that we were drifting toward shipping *firm* business phones as if they were *decision-maker* intel; the doc's value is the principal (name/title/email/phone) + current signals, and a mostly-blank file fails. Redirected enrichment to fight for those cells.
- Google Custom Search kept 403-ing; I cross-checked the diagnosis with a second AI tool, confirmed it was an **IP/account abuse block**, and decided to **drop Google entirely** and pivot to **Wikidata P856** (keyless, no block risk). Verified it returns real sites.
- Caught + fixed a false-match bug (Duquesne Family Office → Duquesne University/duq.edu) by requiring finance-like entity descriptions — honest blank over wrong value.
- Refused to rabbit-hole 990-trustee XML parsing (IRS moved the data); logged it as a known blind spot instead.

**Next:** finish the Wikidata-based enrichment re-run, then fix Rule-2 strictness in validation (it currently over-qualifies on firm name alone) and run validation → dataset.csv.

**Enrichment build + a real failure I hit:**
- Found (by reading the code) that enrichment had no website-finding step and no AUM extraction. Chose DuckDuckGo for lookup (my call), built it + AUM extraction.
- **DuckDuckGo turned out blocked** from this environment (202 anomaly on every variant; direct site fetch works, so only DDG search is blocked). Logged honestly.
- AI suggested a keyless "guess-the-domain + verify" fallback. **I rejected guessing** as dishonest even when verified — see DECISIONS.md. 
- **My decision:** do BOTH, no guessing — (1) a *real* search via a free Google Programmable Search key, and (2) filing-based enrichment (pull principal names/address/phone straight from SEC ADV + Form 990, which also covers no-website SFOs). Email stays an honest blank when unknown.

**Next:** build the filing-based enrichment (#2, no key needed) + the Google search connector (#1, awaiting a free key), then run enrichment.

**Built #2 (filing-based enrichment) — works:**
- Captured the SEC CIK at discovery (it was in `display_names` all along, being thrown away). 80/233 firms now carry a CIK.
- Added `sec_filing.py`: pulls official business phone + address + industry from SEC's submissions JSON (no key), stamped FACT/high confidence because it's an official filing. Tested on 8 firms: **8/8 got a real phone + address** (e.g. Longboat Family Office 212-798-1362, EMFO 954-385-9624). This is the honest no-website answer — real source-backed contacts, never guessed.
- Added AUM extraction (only accepts a $-figure sitting next to asset/AUM/manage language).

**Still pending:** (a) git re-auth as nageen24 (push denied to ewd-ai; commits safe locally); (b) the free Google search key for #1 (website scraping — DDG blocked here). Full enrichment run waits on the Google key so the website-based contacts are real too.
