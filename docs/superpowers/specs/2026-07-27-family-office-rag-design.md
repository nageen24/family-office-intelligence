# Design Spec — Family Office Dataset + Micro-RAG

**Date:** 2026-07-27
**Author:** nageen24
**Assessment:** PolarityIQ / Falcon Scaling — Differentiator Stage 1, Task 1
**Time budget:** ~30h remaining at start of build

> This spec is the plan. The reasoning behind each choice lives in `DECISIONS.md` (kept live during the build). Final graded deliverables (methodology summary, 3 validation chains, RAG doc note, build summary) are written near the end *from* that log.

---

## 1. Goal

Produce **50 unique, qualifying family-office records** (SFO-weighted, verified, actionable) via an automated pipeline, and serve them through a **production-shaped Micro-RAG** with a real grounding control and a customer-facing UI an IR professional can use unaided.

Priority order (theirs, and ours): **dataset → working RAG → presentation.**

---

## 2. Architecture (layers kept separate)

```
[ Discovery ] -> [ Enrichment ] -> [ Validation ] -> [ Dataset (CSV/XLSX + provenance) ]
                                                              |
                                                     [ Ingest / Chunk / Embed ]
                                                              |
                                                        [ Qdrant vector DB ]
                                                              |
                        [ Retrieval layer: structured filter + semantic ]
                                                              |
              [ Grounding control: retrieval gate -> LLM1 answer -> LLM2 reflection/verify ]
                                                              |
                                            [ FastAPI ]  <->  [ Next.js UI ]
```

Three clean layers: **data**, **retrieval**, **presentation** — separate services on Render.

---

## 3. Pipeline components

**3a. Discovery** (8 free source classes, kept separate from proof; SFO-weighted):
SEC Form ADV/13F · Form 990 family-foundation filings · news/press · LinkedIn (person→firm) · state/intl RIA registries · job postings · conference/podcast appearances · OpenCorporates. Output = candidate pool (larger than 50).

**3b. Enrichment**: fill entity attributes (AUM, thesis, mandate), principal contacts (name, title, LinkedIn, email, phone), recent dated signals.

**3c. Validation**:
- **Rule 1 (cells):** every high-value cell carries source + method + confidence + as-of date; unverifiable → honest blank "could not verify."
- **Rule 2 (firm):** affirmative evidence a firm IS an FO before it counts, against a **written SFO proof-standard**. Failing firms → **rejection log**, not the delivered file.
- Findings govern release: a value that fails its check (e.g. undeliverable email) is removed from the customer field and moved to an audit record.

**3d. Output**: `dataset.csv/xlsx` (the 50) + `rejection_log.csv` (discards + reasons) + `scorecard.md` (self-audit).

---

## 4. Dataset schema (per record)

- **Identity/type:** firm_name, firm_type (SFO/MFO/Unconfirmed), type_evidence, website, hq_location, corporate_linkedin
- **Entity intel:** aum (+aum_basis), investing_thesis, mandate, background
- **Principal:** principal_name, title, linkedin, email, phone
- **Signals:** recent_signal, signal_date, signal_type
- **Per high-value cell (separate columns):** *_source, *_confidence (H/M/L), *_epistemic (fact/inference/speculation), *_verified_method, *_asof_date
- **Product scoring:** reachability_score (0–100, weights contactability AND freshness), record_status

---

## 5. Micro-RAG

- **Ingest/chunk:** one record → structured metadata + a text chunk for semantic search.
- **Embeddings:** Gemini free embedding API (light; no local model).
- **Vector DB:** Qdrant free tier.
- **Retrieval:** hybrid — structured filters (type, AUM band, geography) + semantic similarity.
- **Grounding control (the required working control):**
  1. Retrieval-score gate — weak match → decline before answering.
  2. LLM1 — drafts answer from retrieved records only.
  3. LLM2 (reflection) — verifies each claim maps to a record; forces refine / qualify / decline when evidence is insufficient.
- **Two-layer evaluation:** (a) why records are trustworthy (validation), (b) whether live answers stay within records — proven via an **adversarial test set**.

---

## 6. Frontend (customer-facing)

For a non-programmer IR professional: ask a question → readable answer with why-it-matters framing, no internal field names or jargon. Handles success / empty / partial / decline gracefully (no raw JSON or error dumps). Shows the system's own confidence/uncertainty honestly. Every visible word reconciles with the data.

---

## 7. Stack

Python/FastAPI + Next.js, **both on Render (free)** · Gemini free embeddings · Qdrant free · Gemini/Groq free LLM (answer + reflection). Keep-alive ping for Render cold starts. Everything $0.

---

## 8. Differentiators (depth, not padding)

Epistemic layer · reachability score · agentic 2-LLM grounding · uncertainty-showing UI · **rejection log** · **adversarial RAG tests** · **dataset self-scorecard** · **written SFO proof-standard**. Plus documented catches of the assessment's own framing gaps (SFO-vs-contact contradiction, privacy silence, manual/pipeline line, SEC-exemption blind spot, Task 2 bait).

---

## 9. Known blind spots / risks (to state honestly)

- 50 genuinely-verified SFO records in ~13h is the main risk; if sourcing is slow we ship **fewer-but-real over more-but-fake**.
- Free-tier rate limits (Gemini/Qdrant) and Render cold starts.
- SFO contacts are inherently scarce — expect honest blanks on the highest-value firms, by design.

---

## 10. Deliverables mapping

dataset.csv · methodology summary · 3 full validation chains · public repo w/ real history · live Render URL · RAG doc note · build session summary · Task 2 answer. All fed from `DECISIONS.md` + `BUILD_LOG.md`.
