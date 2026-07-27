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
