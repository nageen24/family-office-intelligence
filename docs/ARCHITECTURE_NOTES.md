# Architecture notes

Seven required sections. Every factual claim maps to a real file / log / branch
(the "Where" rows). The reasoning, boundary judgments, tier logic, and "why this
matters" sentences are intentionally left blank for the reviewer to write in their
own words.

---

## 1. Retrieval extension

What is built (artifact map):
- Semantic retrieval over the dataset: `rag/retrieve.py`; embeddings in `rag/embed.py` (`rag/models/potion-base-8M`); vector store ingest in `rag/ingest.py`.
- Structured (deterministic) retrieval for exact constraints/counts: `rag/structured.py` (`search`, `count`, `get_record`).
- Named-firm injection so a firm asked for by name reaches the LLM regardless of embedding score, and lifts the gate: `rag/answer.py`; covered by `tests/test_retrieve.py::test_named_firm_is_injected_even_if_semantics_miss`.
- Type-aware filtering (multi-family query returns MFO + Unconfirmed, never leaks SFO): `rag/answer.py`; `tests/test_retrieve.py::test_type_query_includes_confirmed_and_unconfirmed`.

_Reviewer — what the extension is and why: _____________________________________

## 2. Agentic vs deterministic boundary

What is built (artifact map):
- Deterministic path: corpus counts and exact-constraint reads route to code, not the LLM — `rag/agent.py::is_count_goal` → fixed `count` tool; `rag/structured.py`.
- Agentic path: open goals run an LLM planner + tool loop with a step budget — `rag/agent.py::run_agent`, `llm_planner`, `_tools`, `answer_goal`.
- The mechanical honesty control sits on the deterministic side: a proof quote must be code-verified on the page AND pass the FO-identity gate — `pipeline/ontology.py::quote_present`, `establishes_fo_function`.
- Evidence of the split in practice: `data/goals/` (goal1 ran agentically to `done`; goal2 abstained; count-goals resolve deterministically).

_Reviewer — where you draw the agentic/deterministic line and why: ____________

## 3. Authority boundary

What is built (artifact map):
- Two-LLM separation: a worker/planner drafts; an independent reviewer authority sets release — `rag/agent.py::llm_planner`, `llm_reviewer`, `AgentState.release` (set only by the reviewer).
- Release gate before anything ships: `rag/release_gate.py`, `rag/product.py`.
- Escalation instead of self-deciding: ambiguous records/goals open a human case and stop — `pipeline/escalation.py`, `rag/escalation.py` (`open_case` / `pending_cases` / `resolve_case`), queue file `data/state/needs_human.json`; `tests/test_escalation_detection.py`.
- Withhold authority: validation removes a value from the customer surface and keeps it in audit fields — `pipeline/schema.py::Cell.quarantine`, `pipeline/validation/validate.py`.

_Reviewer — who is allowed to decide what, and why that boundary: _____________

## 4. State, replay, idempotency

What is built (artifact map):
- Durable, committed state keyed by a stable firm key: `pipeline/state.py` (`firm_key`, `load_state`, `save_state`, `unattempted`, `merge_pool`); file `data/state/climb_pool.json`.
- Idempotent climb: an already-attempted firm is skipped, so reruns never duplicate — `pipeline/climb.py::climb_once`; `tests/test_climb.py::test_climb_once_is_idempotent_on_rerun`.
- Restart-safe: state is saved after each batch; a crash loses at most the in-flight batch.
- Replay: raw ordered JSONL traces of agent runs — `rag/replay.py`, `data/goals/*/run_log.jsonl`; per-run summaries `data/state/run_history.jsonl`.
- Re-derivation passes are idempotent: `_retighten_function_proofs` (proof gate), `_recheck_stale` (staleness), `escalate_ambiguous` — all in `pipeline/climb.py` / `pipeline/staleness.py`.

_Reviewer — the state/replay guarantees you rely on and why: _________________

## 5. Cost and latency (incl. what breaks first at 5,000 records)

What is measured (artifact map):
- Cash cost: **$0.00 per run and per record** — all providers free-tier (Groq ×2, Cerebras, Gemini, Serper free credits). Recompute basis in `docs/RECONCILIATION.md`.
- Throughput settings scale with provider count: `pipeline/climb.py::_run_settings` (batch = clamp(18·n,35,120); interval = clamp(20/n,4,10); workers 3/6); `tests/test_climb.py::test_run_settings_scale_with_provider_count`.
- Per-run token math and the daily ceiling: `docs/FAILURES.md` (Groq TPD exhaustion), `docs/DATA_HONEST_LIMITS.md`.
- Binding constraint is **tokens-per-day**, not cash: ~3.4k tokens/firm; per-provider free TPD ~500k; ≈150 firms/day/provider (`docs/RECONCILIATION.md`, `docs/DATA_HONEST_LIMITS.md`).
- At scale, candidate ordering keeps highest-yield first: `pipeline/discovery/sec_adv.py::priority_score`, `pipeline/build_candidates.py::interleave_name_only`.

Facts relevant to "at 5,000 records, what breaks first and at what volume":
- LLM tokens-per-day is the first ceiling (per-provider TPD; see the 429 exhibit in `docs/FAILURES.md`).
- SMTP verification of personal emails is blocked from cloud IPs (port 25) → emails stay `inferred` (`docs/DATA_HONEST_LIMITS.md`).
- Serper free-tier daily query cap guards LinkedIn/website lookups: `pipeline/enrichment/serper.py` (`daily_quota_ok`, `data/state/serper_quota.json`).

_Reviewer — which limit breaks first at 5,000, at what volume, and the fix: ___

## 6. What broke while building

What is documented (artifact map):
- Groq tokens-per-DAY exhaustion (mass silent enrichment failure) → fix (per-model 8b + round-robin) → recovery run: `docs/FAILURES.md` §1, fix commit `93c9f8d`.
- Empty Serper key silently no-op'd LinkedIn recovery for 7 runs: `docs/FAILURES.md` §2.
- CI `git add` missing-pathspec lost ALL state ("no changes to commit"): fix commit `1b26d1b`; `.github/workflows/climb.yml`.
- Browser website-finder returned nothing (Bing redirect encoding); fixed by decoding `u=a1<base64>`: `pipeline/enrichment/render.py::_debing`; `tests/test_render_debing.py`.
- Cerebras + Gemini failing 100% of calls (dead weight) surfaced by per-provider health: `rag/llm.py::provider_stats`; `data/state/run_history.jsonl` `provider_health`.
- Proof gate over/under-correction (serve-families accepted; then bare-predicate rejected): `pipeline/ontology.py::establishes_fo_function`; `tests/test_fo_function_gate.py`.

_Reviewer — the lesson you take from what broke: ______________________________

## 7. Commercial tier logic

What is built (artifact map):
- Inclusion floor (counts toward the set): qualifying category + exists + FO-function + entity-coherent + ≥1 beyond-seed cell + a personal reach route — `pipeline/ontology.py::meets_inclusion_floor`.
- Commercial standard (worth-buying flag, not a gate): decision-maker + focus/mandate + reachable route + dated signal — `pipeline/ontology.py::meets_commercial_standard`; surfaced as `is_commercial` in `data/final/dataset.csv`.
- Per-record transparency labels the buyer sees: `category`, `is_commercial`, `has_investing_focus`, `has_recent_signal`, per-cell `__status` / `__route` — `pipeline/schema.py::to_flat_row`.

_Reviewer — the commercial tiers, who each is for, and the pricing/packaging logic: ___

---

_All narrative/judgment lines above are intentionally blank for the reviewer._
