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
