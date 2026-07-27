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

## Session 5 — 2026-07-27 — 13F breakthrough + honest yield reckoning

**Honest yield check first:** the Wikidata-based run's real numbers (counted by value, after I caught my own misleading 100% count) were: signals 65%, firm phone 32%, but websites 4%, principal name 1%, email 0%, AUM 0%. I said plainly: this file would fail the actionability bar as-is.

**What the AI produced:** the 13F enrichment module (signature name/title/phone + portfolio value), value-convention disambiguation, ADV probes (all 403-blocked from this IP), and the DECISIONS entries.

**What I decided / changed on top of it:**
- Adopted the **13F insight** as the sourcing centerpiece: FOs are ADV-exempt but NOT 13F-exempt, so 13F filers named "Family Office" are provable SFOs — the exemption blind spot became the targeting mechanism.
- **Honest labeling rule (mine):** 13F values are labeled "13F portfolio value", never "AUM" — a correct conservative number over an inflated one.
- Confirmed dropping ADV after it proved IP-blocked (third blocked service; no more rabbit-holes).
- Caught-in-testing bugs logged: mixed thousands/dollars convention ($108T absurdities), corporate signers as "principal names", $0 values.

**Next:** re-run enrichment with 13F, then STRICT Rule-2 validation → dataset.csv + rejection_log.csv + SFO/MFO split.

## Session 6 — 2026-07-28 — Recovering websites/emails + honest SFO reclassification

**What the AI produced:** the 13F/registry pipeline results, and the honest report that website/email cells were nearly empty because every scripted search engine IP-blocks this environment (it tested 7; Bing served a Cloudflare bot-challenge). Its recommendation was to accept the gap and leave those cells blank marked "could not verify."

**What I decided / changed on top of it:**
- **I refused to stop at the blank.** My idea: a real browser isn't blocked (we'd used Chrome fine earlier), so route the website search *through Chrome* — drive Bing in a genuine browser session and read the result domains. That got us past the IP block that killed every API.
- **My second idea: verify every result in code before trusting it.** Search top-hits are often the wrong company sharing a word (Looper→looper.com the film, Duquesne→finnotes, Genspring→truist). I had us add `verify_websites.py`: fetch each candidate directly, accept only if the firm's distinctive name + family-office context is on the page (or the domain itself proves it); scrape emails only from verified same-domain pages; MX-check them in validation.
- Result: ~4 → ~29 verified websites, ~8 verified emails, zero false matches shipped. Unverifiable firms keep an honest "could not verify" blank (Rule 1 candor), never a guess.
- **I also corrected an over-labeling error I'd approved earlier:** filing a 13F under a family-office name proves it's a family office, not a *single*-family one. Reclassified 13F-only firms from SFO to Unconfirmed — honest, avoids the "most serious error" of presenting an unconfirmed firm as a proven SFO.

**Reasoning captured in DECISIONS.md (2026-07-28 entries), framed as my calls.**

## Session 7 — 2026-07-28 — RAG build (Phase 2)

Built the Micro-RAG via brainstorming → spec → TDD plan → inline execution (5 tasks, test-first, committed per task).

**What the AI produced:** ingest (records→embeddings→Qdrant), hybrid retrieval + score gate, the agentic 2-LLM answer layer, FastAPI backend, adversarial test set. 13 tests (9 fast + 4 live traps) all pass.

**What I decided / changed on top of it:**
- The grounding control is **my** design: LLM-1 answers, LLM-2 validates (approve/refine/decline) before the user sees anything — logged in my words. Live-verified it declines fabricated emails and non-existent figures.
- **Embeddings pivot (my call):** torch + onnxruntime both DLL-failed on Python 3.14 (Windows); rather than force a new Python or a paid API, switched to **model2vec** (pure NumPy, keyless, works dev+deploy).
- **In-memory Qdrant (my call):** local file mode locks to one process so a server can't use it; rebuild the 66 vectors in memory at startup — no lock, no external DB, deploys anywhere.
- Building the RAG **surfaced a data bug I fixed**: Pathstone (a real multi-family office) was mislabeled SFO via the weak marker "one family" (MFO marketing). Tightened the SFO markers → honest SFO count is 3.

**Error handling (my calls, hardening the answer layer):**
- I asked for proper failure handling. Added distinct user-facing states — empty / no_match / declined / answered / **error** — each a readable message, never an error dump (matches the doc's success/empty/partial/failure requirement).
- **My decision: two LLM keys with failover.** Both LLMs try Groq first, then fall over to OpenRouter (`openai/gpt-oss-20b:free`) if Groq is down/rate-limited — so a single provider outage can't take the system down. Only if both fail does the user see an honest "service unavailable" message. Logged in DECISIONS.md in my words. Failover unit-tested (Groq-fails→NVIDIA-serves, all-fail→error, no-keys→error).

**Next:** Phase 3 — the live customer-facing UI on top of this API + deploy.

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
