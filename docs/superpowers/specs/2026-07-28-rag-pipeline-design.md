# Micro-RAG Pipeline — Design Spec

**Date:** 2026-07-28
**Builds on:** the 66-record validated dataset (`data/final/dataset.csv`) from Phase 1.
**Owner decisions:** see `DECISIONS.md` (agentic 2-LLM grounding is the candidate's own call).

---

## 1. Goal & what the assessment demands

Make the dataset queryable in natural language by a **non-programmer IR
professional**, through a **live customer-facing URL**, with a **mechanical
grounding control** that makes the system qualify/limit/decline rather than
hallucinate. The dataset is the product; this is the delivery mechanism.

Requirements pulled directly from the assessment (each is honoured below):
- Production-shaped, deployable — **not** localhost/notebook/single-process.
- **Structured retrieval AND semantic retrieval** (both).
- A **working grounding control** — prompt instructions alone are insufficient.
- Test **both layers** (records, and the generated answers).
- Handle **success / empty / partial / failure**, each with a readable message.
- **Separation of retrieval, data, and presentation layers.**
- Customer UI: no field names, no jargon, no raw JSON, no error dumps.
- Every visible word is a claim; the UI must not over-promise.

## 2. Architecture — four separated layers

```
[ Data layer ]      dataset.csv + provenance  (source of truth, read-only)
      |  ingest (one-time): one text blurb + structured metadata per firm
      v
[ Retrieval layer ] Qdrant vector store + structured filters
      |  hybrid: structured filter  +  semantic search  +  score gate
      v
[ Answer layer ]    LLM-1 answerer  ->  LLM-2 validator (approve/refine/decline)
      |  only an approved/qualified answer, or an honest decline, leaves here
      v
[ Presentation ]    FastAPI  ->  web UI (IR-professional language)
```

Each layer is a separate module with a defined interface, independently testable:
- `rag/ingest.py` — records → chunks + metadata → embeddings → Qdrant.
- `rag/retrieve.py` — query → (filters + semantic) → ranked records + scores.
- `rag/answer.py` — records + question → LLM-1 → LLM-2 → final verdict+text.
- `rag/api.py` — FastAPI endpoints (`/search`, `/answer`, `/health`).
- `frontend/` — the customer UI (Phase 3, separate spec if needed).

## 3. Ingest (one-time, 66 records)

Per record, build:
- **Text blurb** — readable prose: name, type, AUM, principal + title, location,
  recent signal, thesis. This is what gets embedded/semantically searched.
- **Structured metadata** — `firm_type` (SFO/MFO/Unconfirmed), `aum_band`,
  `location`, `has_email`, `has_phone`, `signal_date` — for exact filtering.
- Carry the **provenance** through so the answer layer can cite basis.

## 4. Retrieval — hybrid + score gate

1. **Structured filter first** when the query implies it ("SFOs over $1B in
   New York" → filter firm_type=SFO, aum_band≥1B, location=NY).
2. **Semantic search** over the filtered set (embedding cosine similarity).
3. **Retrieval-score gate** — if the top score is below a threshold, return
   "no confident match" and STOP (decline before spending the LLMs). This is
   the cheap first guard of the grounding control.

## 5. Grounding control — the agentic 2-LLM validator (candidate's decision)

The core mechanism (full reasoning in `DECISIONS.md`, 2026-07-28):
- **LLM-1 (Answerer)** — drafts an answer using ONLY the retrieved records.
- **LLM-2 (Validator)** — separate call; sees LLM-1's draft + the same records;
  narrow adversarial mandate: *is every claim supported? is anything
  overstated? is the evidence enough?* Returns **approve / refine / decline**.
  - approve → send. refine → rewrite to only what's supported, send.
    decline → honest "can't answer confidently from the data."
- The user never sees an unchecked answer. A prompt cannot guarantee obedience;
  a separate evaluator with a decline power mechanically can.

## 6. Failure / empty / partial handling

Every non-happy path returns a plain-English message, never an error dump:
- **Empty** (no record matches) → "No family office in the dataset matches that."
- **Partial** (matched, but the asked cell is blank) → answer what's known +
  "we don't have a verified email for this firm" (mirrors the honest blanks).
- **Decline** (LLM-2) → "The data doesn't support a confident answer here."
- **System error** → generic readable apology, logged server-side.

## 7. Testing both layers (assessment requirement)

- **Data layer** — already covered by Phase-1 validation + provenance.
- **Answer layer** — an **adversarial test set**: trap questions designed to
  make it hallucinate or over-claim (e.g. "What is the email of [firm with a
  blank email]?", "Which SFO manages $50B?" when none does), with recorded
  proof the system **declined or qualified** instead. Stored as
  `rag/adversarial_tests.md` + a runnable check.

## 8. Stack (provider) — decision & fallback

- **LLMs:** **Groq on two independent keys (primary + backup failover)** (candidate
  decision, logged). LLM-1 and LLM-2 both call a chain: Groq key 1
  (`llama-3.3-70b-versatile`) first, and on any failure the same call falls over to
  Groq key 2 on a separate account. Two independent keys = no single point of
  failure; only if both fail does the user get the honest `error` state. Neither
  is Google, so both dodge the IP-flag that blocked earlier search work.
- **Embeddings:** **local `all-MiniLM-L6-v2`** (sentence-transformers, ~80MB) —
  keyless, no Google dependency, computes 66 vectors once and only embeds the
  short user query at runtime (light enough for a free-tier host). Gemini
  embedding API is the alternative but re-introduces the Google dependency;
  local is the safer default given the environment. **To confirm with user.**
- **Vector store:** **Qdrant** — local file-mode for dev, Qdrant Cloud (free)
  for deploy.
- **Backend:** FastAPI. **Deploy:** Render (per earlier stack decision).

## 9. Out of scope (YAGNI)

No auth, no multi-user accounts, no streaming, no re-ranking models, no
conversation memory. One question → one grounded answer. Small by design.

## 10. Stack decisions (confirmed 2026-07-28)

1. **Embeddings: local `all-MiniLM-L6-v2`** — keyless, no Google dependency. ✅
2. **LLMs: Groq `llama-3.3-70b`** — key saved in `.env`, tested working (200 OK).
   Chosen over Gemini specifically because Groq is not Google and is unaffected
   by the IP-flag that blocked Custom Search. ✅
3. **Qdrant: local (file mode) for dev**, Qdrant Cloud (free) at deploy. ✅
