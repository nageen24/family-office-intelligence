# Implementation Plan — Family Office Dataset + Micro-RAG

**Repo:** https://github.com/nageen24/family-office-intelligence
**Spec:** `docs/superpowers/specs/2026-07-27-family-office-rag-design.md`
**Live reasoning:** `DECISIONS.md` · **Build sessions:** `BUILD_LOG.md`
**Started:** 2026-07-27, ~30h left in the 48h window.

---

## HOW TO RESUME (read this first if starting in a new chat)

1. Read this file, then `DECISIONS.md`, `BUILD_LOG.md`, and the spec.
2. Memory has the full context (`master-build-plan` + linked notes).
3. Check the Progress Tracker below for where we stopped.
4. Golden rules while building:
   - **Priority order:** dataset → working RAG → presentation.
   - Commit + push after every meaningful step (real history, never squash).
   - Log every decision to `DECISIONS.md`; log each session to `BUILD_LOG.md`.
   - Surface candidate-judgment choices to the user before writing them as "my decision."
   - Never fake verification. Honest blanks over guesses. Findings govern release.
   - $0 stack. Keep the assessment doc OUT of the repo.

---

## PROGRESS TRACKER

- [x] Brainstorm + design decisions
- [x] Spec written
- [x] Decision log + build log started
- [ ] **Phase 1 — Dataset pipeline** ← NEXT
- [ ] Phase 2 — RAG + grounding
- [ ] Phase 3 — Frontend + deploy
- [ ] Phase 4 — Task 2 analysis
- [ ] Phase 5 — Final deliverable docs
- [ ] Submit (single email to optimize@falconscaling.com, request receipt)

---

## PHASE 1 — Dataset pipeline (~13h, PASS/FAIL)

Goal: pipeline produces 50 qualifying records + rejection log + scorecard. Not hand-assembled.

1. **Scaffold** repo structure: `pipeline/` (discovery, enrichment, validation), `data/` (raw, interim, final), `rag/`, `frontend/`, `config/`. Add `.gitignore`, `requirements.txt`, `.env.example` (no secrets committed).
2. **Discovery modules** (one per source class, kept separate; output = candidate pool with `discovery_source` tagged):
   SEC ADV/13F · Form 990 foundations (ProPublica) · news/press · LinkedIn (person→firm) · state/intl registries · job postings · conferences/podcasts · OpenCorporates.
3. **Dedup + normalize** the candidate pool.
4. **Firm-type classifier + SFO proof-standard** (Rule 2): only firms with affirmative FO evidence pass; label SFO/MFO/Unconfirmed with `type_evidence`. Failures → `rejection_log.csv`.
5. **Enrichment** modules: entity attrs (AUM, thesis, mandate, background), principal (name/title/LinkedIn/email/phone), recent dated signals.
6. **Validation** (Rule 1): per-cell source + method + confidence + as-of date; email/phone verified by free-tier tool + independent free cross-check. Failed values removed from customer fields → audit record.
7. **Assemble outputs:** `data/final/dataset.csv` (50 qualifying), `rejection_log.csv`, `scorecard.md`.

## PHASE 2 — RAG + grounding (~6h)

1. Ingest records → structured metadata + text chunk per record.
2. Embeddings via Gemini free API → store in Qdrant (free).
3. Hybrid retrieval: structured filters (type, AUM band, geography) + semantic.
4. Grounding control: retrieval-score gate → LLM1 answer (records only) → LLM2 reflection/verify → refine / qualify / decline.
5. Adversarial test set: trap questions + recorded proof the system declined/qualified.

## PHASE 3 — Frontend + deploy (~5h)

1. FastAPI backend exposing search + answer (separate from data + presentation).
2. Next.js UI: IR-professional language, why-it-matters framing, graceful success/empty/partial/decline, shows own uncertainty, no jargon/JSON.
3. Deploy both as Render services ($0); keep-alive ping for cold starts.
4. Personally run real queries; record them for the doc note.

## PHASE 4 — Task 2 (~2h)

SaaS free→paid conversion analysis. Diagnose the specific FO-SaaS conversion problem before prescribing; refuse the generic playbook (framed as bait). Candidate's own reasoning, visible.

## PHASE 5 — Final docs (~3h, written from the live logs)

Methodology summary · 3 full validation chains · RAG doc note (incl. actual live queries run) · build session summary (AI vs my changes, honest hours). Reconcile every count/label with the artifacts.

---

## Sub-agent plan (parallelization during Phase 1–2)

The 8 discovery modules are independent → good candidates for parallel sub-agents once the scaffold + shared schema/interfaces exist. Dispatch one agent per source (or small batches), each writing to the shared candidate-pool format. Enrichment/validation also parallelizable per record batch. Do NOT dispatch agents before the scaffold and interfaces are defined (they need a stable contract to write against).

## Key risks (state honestly in final docs)

- 50 genuinely-verified SFO records in ~13h — main risk; ship fewer-but-real over more-but-fake.
- Free-tier rate limits (Gemini/Qdrant); Render cold starts.
- SFO contacts inherently scarce → expect honest blanks on the highest-value firms.
