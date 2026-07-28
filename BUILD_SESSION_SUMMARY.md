# Build Session Summary

**Approximate build time:** ~2 working days (the 48-hour window), in the sessions
below. Reported plainly, not padded.

## Main work sessions
1. **Design + dataset schema** — defined the family-office categories (SFO / MFO /
   Unconfirmed), the two rules of proof (cell-level vs firm-level), the epistemic
   layer (fact / inference / speculation + confidence + as-of date + source), and
   the reachability score. Wrote the SFO proof standard.
2. **Discovery pipeline** — multi-source: SEC CIK registry, SEC EDGAR full-text,
   Google News RSS, ProPublica 990s, OpenCorporates, Wikidata. 281 candidates
   into the pool.
3. **Enrichment** — SEC submissions JSON (phone/address), 13F primary_doc
   (principal signature + portfolio value), website discovery, news signals.
4. **Validation + delivery** — firm-level qualification, rejection log, value
   ranking to select the top 50; CSV/XLSX output.
5. **Micro-RAG** — ingest → local embeddings → in-memory Qdrant; hybrid retrieval
   + score gate; two-LLM grounding control; FastAPI; Vercel deploy.
6. **Live-product hardening** — the customer UI, failure states, and several bugs
   I caught by using the deployed system as a client would (below).
7. **Task 2** — SaaS conversion analysis.

## For the major components: what the AI produced vs what I changed/decided
- **Grounding control** — my design decision (two-LLM answerer/validator, Ng
  reflection pattern), not an off-the-shelf suggestion. I later scoped the
  validator to detail queries and made list/rank answers deterministic.
- **Embeddings** — the AI first proposed torch/sentence-transformers; it wouldn't
  load on Python 3.14/Windows. I switched to model2vec (pure NumPy, keyless).
- **Hosting** — I rejected the initial split-hosting plan; consolidated to one
  deployable serverless surface.
- **Bugs I caught after the AI called it "done" (the important part):**
  - Live system answered "8 family offices" (should be 50) — the count came from
    the retrieved slice, and the searchable blurb had dropped phone/email/website,
    so contact questions were being declined despite the data existing. Fixed both.
  - Whole classes of question failed silently: named-firm lookups (the firm was
    never retrieved) and aggregates (top-k can't answer "largest AUM"). Fixed with
    named-firm injection + whole-corpus retrieval.
  - Type questions returned only "confirmed" firms; I designed the graded answer
    (confirmed / likely-by-name / unproven) so the honest count doesn't read as a
    thin dataset.
  - **AUM parsing bug** — several 13F values were inflated 1000x (CVA "$949B") by a
    thousands-vs-dollars mistake. I re-derived the disambiguation from the $100M
    13F threshold + average-position sanity, and corrected them (false data must
    not ship).
  - **Principal names** — the 13F extractor read the wrong XML block, so only 3/50
    firms had a named decision-maker. Scoped it to the signature block and
    backfilled to 34/50, all official-filing-sourced.

Full reasoning for each decision is in `DECISIONS.md`; the running narrative is in
`BUILD_LOG.md`.
