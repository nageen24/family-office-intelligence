# RAG Documentation Note

A short, honest note on the Micro-RAG: the stack, how it retrieves, what works,
what doesn't, the live queries I actually ran, and what I'd improve.

## Stack choices
- **Backend:** Python + FastAPI (`rag/api.py`), deployed as a Vercel serverless
  function (`api/index.py`). Chosen so the same code runs locally (`uvicorn`) and
  on a real URL with no separate server to babysit.
- **Vector store:** Qdrant, run **in-memory** and rebuilt at process start from
  `data/final/dataset.csv` (~50 vectors, ~1s). In-memory (not the local file
  store) because the file store takes a single-process lock a web server can't
  share, and because it means the deploy needs no external vector DB.
- **Embeddings:** `minishlab/potion-base-8M` via **model2vec** — a distilled
  static embedding that runs on pure NumPy. This was a forced, deliberate choice:
  torch, onnxruntime, and fastembed all failed to load on this Python 3.14 /
  Windows box (native DLL init errors), and I didn't want a paid embedding API.
  model2vec has no native ML runtime, is keyless, and works both in dev and on the
  Linux deploy target. Trade-off: static embeddings are a notch weaker than a full
  transformer on nuance — acceptable for 50 records and short IR-style queries.
- **LLMs:** two providers with automatic failover — Groq (primary,
  `llama-3.3-70b-versatile`) then OpenRouter (`openai/gpt-oss-20b:free`). Both
  OpenAI-compatible; if the primary is down/slow the same call runs on the backup.

## Chunking strategy
**One record = one chunk.** Each firm becomes a single human-readable blurb
(`rag/ingest.py:record_to_blurb`) carrying every high-value cell (type, location,
AUM, principal, phone, email, website, thesis, mandate, recent signal). No
sub-document splitting: the records are short and self-contained, and a client's
question is almost always about a firm, so the firm is the natural retrieval unit.
The blurb is both what gets embedded and what the answer LLM sees — so a cell that
isn't in the blurb can't be answered (a bug I caught and fixed: contact cells were
originally missing from the blurb).

## Retrieval approach (hybrid + graded controls)
1. **Structured pre-filter** (`rag/retrieve.py:_filters`): firm-type (SFO/MFO,
   plus Unconfirmed for type questions) and has-email, matched from the query.
2. **Semantic search**: cosine over the model2vec vectors.
3. **Named-firm injection**: if the query names a firm in the corpus, that exact
   record is pulled in regardless of embedding score (a weak static embedding
   barely moves for a proper noun, so a named firm would otherwise be missed).
4. **Score gate**: if nothing clears a minimum similarity, the system declines
   rather than answer from weak matches.
5. **Whole-corpus path**: list / rank / count / type questions retrieve all 50 so
   the answer reasons over the full set, not a top-k slice.

## Grounding control (the required "limit what an answer may claim")
An **agentic two-LLM control** (Andrew Ng reflection pattern):
- **LLM-1 (answerer)** drafts from only the retrieved records.
- **LLM-2 (validator)** audits the draft against the same records and returns
  APPROVE / REFINE / DECLINE — the user never sees an unchecked answer.
- Deterministic answers (firm-type lists) skip the LLMs entirely — they're a
  mechanical read of structured fields, so they can't hallucinate and can't time
  out. The validator is scoped to the detail / natural-language answers where a
  fabricated email or figure is the real risk.
- Distinct user-facing states: answered / declined / no-match / empty / error —
  each rendered as readable copy, never a raw dump.

## What works
- Named-firm lookups, type lists (graded confirmed / likely / unproven tiers),
  aggregates (largest AUM, counts), and honest declines on off-topic queries.
- Deployed, layer-separated (data / retrieval / answer / presentation), 20 tests.

## What doesn't / limits
- Free-tier LLM latency is spiky; whole-corpus LLM answers can take 20–40s. I
  moved list/rank to deterministic paths to keep them fast, but a busy Groq still
  makes some detail answers slow.
- Static embeddings miss subtle semantic matches a transformer would catch; the
  named-firm injection and structured filters are there partly to compensate.
- Recent-signal coverage in the data (17/50) limits "why now" answers for ~2/3 of
  firms.

## Live queries I actually ran against the deployed URL
(https://family-office-intelligence.vercel.app)
- "family offices in New York" → correct list, grounded. ✅
- "list all multi family offices" → three tiers (2 confirmed, 4 likely by plural
  name, rest unproven). ✅ (caught here that shorthand "multi fo" missed detection;
  fixed.)
- "which firm has the largest AUM?" → correct after the AUM units fix. ✅
- "what is the email of Duquesne Family Office?" → "not available" + Duquesne
  correctly retrieved (honest, not a blanket decline). ✅
- "tell me about Biltmore Family Office" → clean labelled bullets (caught the
  answer rendering as a run-on paragraph; fixed with formatting + pre-wrap). ✅
- "how do I bake sourdough bread" → declined (score gate holds). ✅

## What I'd improve with more time
- A stronger embedding (transformer) once the runtime issue is solved, to reduce
  reliance on lexical injection.
- Freshness: a scheduled re-pull of recent signals so "why now" is answerable for
  most firms — this is also the core of the Task 2 product thesis.
- Cache the built index across serverless invocations to cut cold-start latency.
