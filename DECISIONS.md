# Decision Log

Running log of decisions, tradeoffs, and uncertainties during the build.
Rough and honest by design — not polished. Dated as decided.

---

## 2026-07-27 — Discovery sources (pass/fail core)

**Decision:** Use 5 free discovery sources, weighted toward finding hidden single-family offices (SFOs):
1. SEC Form ADV / 13F — official existence + AUM proof
2. Form 990 family-foundation filings (ProPublica Nonprofit Explorer) — back-door to invisible SFOs via shared staff/address
3. News / press (deal + hire announcements) — surfaces active SFOs + dated recent-activity signals
4. LinkedIn (person title → firm) — reverse-map hidden SFOs with no website
5. State / international RIA registries — secondary official cross-check

**Refused:** Curated directories as a *primary* source — too MFO-heavy, would inherit their bias and risk the single-source-copy penalty. Kept only as a last-resort lead, never as proof.

**Key domain insight driving the split:** Family offices are largely *exempt* from SEC registration (the Family Office Rule), so the purest SFOs are often invisible to Form ADV. That is why discovery leans on 990s, news, and LinkedIn to *find* hidden SFOs, while SEC/registries are used mainly to *prove* the ones found. Discovery job and proof job kept separate.

**Uncertainty:** How many genuine SFOs (vs MFOs) the free sources will actually surface within 48h is unproven — this is the main risk to hitting 50 qualifying records. To validate.

---

## 2026-07-27 — Verification approach

**Decision:** Each high-value cell (email, phone, LinkedIn, AUM) verified by a free-tier check + at least 1 independent free cross-check (firm site / LinkedIn / filing). Target $0 (assessment states no paid tools required). A verification tool is an instrument, not a discovery source.

**Reasoning:** They check a sample; two independent sources agreeing survives that check. One tool alone is weak.

---

## 2026-07-27 — Grounding control (RAG)

**Decision:** Use an agentic two-LLM validation (Andrew Ng reflection pattern): LLM1 answers from retrieved records; LLM2 verifies each claim against the records and forces refine / qualify / decline when evidence is insufficient. Layer with a retrieval-score gate and a claim-to-citation check.

**Reasoning:** Prompt instructions alone don't prove the model obeys — a mechanical control does.

---

## 2026-07-27 — Approved differentiators

Flaws to surface in the assessment's own framing: (1) SFO contradiction — hidden firms vs rich-contact demand; (2) privacy sensitivity of collecting personal contacts (still collect, but note awareness, use public business contacts); (3) define our own explicit manual-vs-pipeline line (pipeline produces every record; humans only verify/reject, never create).

Depth features to build: (4) epistemic layer — every cell tagged fact/inference/speculation + confidence + freshness date + source; (5) reachability/actionability score per record; (6) agentic 2-LLM grounding; (7) UI that shows its own uncertainty and declines honestly.

---

## 2026-07-27 — Dataset schema

**Decision:** Per-record fields grouped as: firm identity + type (with type_evidence for Rule-2 proof), entity intelligence (AUM, thesis, mandate, background), principal decision-maker (name, title, LinkedIn, email, phone), recent dated signals (signal, date, type), epistemic+provenance layer per high-value cell (source, confidence, fact/inference/speculation, verify-method, as-of date), and product scoring (reachability_score, record_status).

**Provenance format:** separate columns per cell (not JSON) — evaluators can check a cell's basis fast.

**Reachability score:** combines BOTH contactability (email/phone present) AND freshness (recent dated signal) — a record is actionable only if you can both reach them and have a reason to reach them now. Exact weights to tune during build.

---

## 2026-07-27 — Infrastructure / hosting (my call, after rejecting the initial AI plan)

The AI first proposed hosting the frontend on Vercel with a **local embedding model** (torch/sentence-transformers), and later a Vercel-frontend + Render-backend split. I pushed back on both. My priority is a clean, smooth deployment with no platform-fighting and no surprises, so I made two changes:

**1. Embeddings — hosted API, not a local model.** A local embedding model is heavy on memory, and free-tier hosts have very little RAM — that's a recipe for a service that chokes or crashes. I chose **Gemini's free embedding API** instead: it keeps the backend lightweight, deploys anywhere without memory limits, and stays $0. Tradeoff I accepted: a dependency on the free-tier rate limits and internet, which I judged acceptable for a 50-record dataset.

**2. One platform — everything on Render.** Rather than splitting across Vercel + Render, I consolidated both the Next.js frontend and the FastAPI backend onto **Render** as two separate services. This gives me one place to manage, less context-switching and less mess, while still keeping the layers separated (two services, not one merged app). Tradeoff I accepted and will mitigate: Render's free tier sleeps after ~15 min idle (~50s cold start), which I'll handle with a keep-alive ping so the live demo stays responsive.

**Final stack:** Python/FastAPI + Next.js, both on Render (free); embeddings via Gemini free API; Qdrant free vector DB; Gemini/Groq free LLM for the answer + reflection layers.

