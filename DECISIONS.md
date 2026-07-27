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

**Added after self-review (I asked: are we missing an important source?):** Before locking the list I deliberately checked it for blind spots and added three more, all aimed at the hidden-SFO problem:
- **Job postings** (LinkedIn / Indeed) — an SFO quietly hiring a CIO/analyst exposes its existence even with no website. Strong, under-used SFO signal.
- **Conference speaker/attendee lists + podcasts** — principals appear publicly here even when the firm doesn't.
- **OpenCorporates / company registries** — for entity/existence proof.

Reasoning: my original 5 leaned on filings and news; adding people-driven and hiring-driven sources widens discovery toward exactly the invisible SFOs the assessment values most, and further guards against single-source bias.

---

## 2026-07-27 — Standout additions I'm committing to (depth, not padding)

1. **Rejection log.** I keep every firm my system found but *threw out*, each with a reason (couldn't confirm it's an FO / email bounced / MFO-relabel risk / duplicate). The doc says validation that doesn't change what you deliver "is not validation, only measurement" — the rejection log is my proof the validation actually changed the output. Most candidates show only the 50 winners; I show the discards too.

2. **Adversarial RAG test set.** A deliberate set of "trap" questions built to make the system lie, over-claim, or answer beyond the data — with recorded proof it qualified or declined instead. This tests the *answer* layer (not just the data layer) and demonstrates my agentic 2-LLM grounding control actually holds.

3. **Dataset self-scorecard.** An honest one-page summary of my own product: % of records with verified email/phone, SFO vs MFO split, and the blind spots that remain. Self-grading the product rather than hiding its weak spots.

4. **Written SFO proof-standard.** An explicit, stated evidence bar a firm must clear before I label it a single-family office — so "SFO" is a proven classification in my file, not a hopeful guess. Directly serves the assessment's stricter firm-level rule (Rule 2).

## 2026-07-27 — Additional flaws I caught in the assessment's own framing

(Adds to the three already noted: SFO-vs-contact contradiction, privacy silence, fuzzy manual-vs-pipeline line.)

- **Existence-proof blind spot.** The assessment leans on "prove the firm exists/what it is," but family offices are largely *exempt* from SEC registration, so the most genuine SFOs are invisible to the very filing sources that "proof" usually relies on. Their framing quietly assumes findability that doesn't hold for the highest-value records — which is exactly why my discovery is weighted toward 990s, hiring signals, news, and people, not filings alone.
- **Task 2 is framed as bait.** Stating that "all major LLMs failed catastrophically" is designed to provoke a generic, over-engineered answer. I read it as a prompt to diagnose the specific family-office-SaaS conversion problem before prescribing, and to refuse the reflexive playbook answer.

---

## 2026-07-27 — Dropped LinkedIn / job boards / conferences as discovery sources (my call)

I originally planned 8 discovery sources, including LinkedIn, job boards, and conference/podcast lists. When it came to building them I hit a wall: automated scraping of those sites violates their ToS and is actively blocked, so any scraper would either return nothing or need me to hand-collect firms into a file. The assessment explicitly forbids manual compilation of records (only manual spot-checks/judgment calls are allowed), and I refuse to fill the dataset with fake or hand-assembled entries just to inflate the source count.

**Decision:** remove those sources entirely rather than fake coverage or smuggle in manual compilation. I'd rather stand on fewer, genuinely automated sources than claim breadth I didn't earn. The pipeline now discovers from **4 clean automated source classes** — SEC EDGAR, ProPublica 990 (family foundations), Google News, OpenCorporates — which are still genuinely diverse (regulatory filings, nonprofit filings, press, and company registries), so this is real multi-source discovery, not one source copied at scale.

**Tradeoff / uncertainty I accept:** fewer sources could mean fewer raw candidates; if 4 sources don't yield 50 qualifying records, I'll widen queries within these sources before I ever add a fake or manual one. Honesty of the file comes first.

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

