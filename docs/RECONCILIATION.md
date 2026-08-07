# Reconciliation — every number, recomputed from the final files

Single source of truth. Every figure here is recomputed directly from a committed
file or the git log (command shown), so no two documents disagree. Judgment,
tier-logic, and "why this matters" sentences are intentionally left blank for the
reviewer.

## Records

| Number | Value | Source (recompute) |
|---|---:|---|
| Qualifying records (shipped) | **2** | `data/final/dataset.csv` row count |
| — by source class | ADV: 2 | `dataset.csv` `discovery_source` |
| — by firm type | MFO: 1, FO-type-unknown: 1 | `dataset.csv` `firm_type` |
| Function-proven firms | 8 | `climb_pool.json` where `proof_function_quote` set |
| Attempted firms (full funnel) | 648 | `data/state/climb_pool.json` record count |

The two qualifying records are ALPHA CAPITAL FAMILY OFFICE and SESTANTE FAMILY
OFFICE. The other 6 proven firms have no personal reach route.

_Reviewer note:_ ______________________________________________________________

## Emails (200-personal gate)

| Number | Value | Source |
|---|---:|---|
| Verified personal emails | **0** | `dataset.csv` status=verified & route=personal |
| Inferred personal emails | 0 | `dataset.csv` status=inferred & route=personal |
| Gate | 200 | fixed target |
| Shortfall | 200 | 200 − 0 |

Honest miss, documented in `docs/DATA_HONEST_LIMITS.md` (SMTP port 25 blocked from
this environment; emails rarely published; Apollo People API paid-only).

_Reviewer note:_ ______________________________________________________________

## Runs and cost

| Number | Value | Source (recompute) |
|---|---:|---|
| Scheduled runs | 19 | `git log --grep "climb: scheduled run" | wc -l` |
| Operating span | 76.0 h | first (2026-08-04 03:35Z) vs latest (2026-08-07 07:33Z) scheduled-run commit |
| Run-history entries | see file | `data/state/run_history.jsonl` line count |
| Cash cost per run | **$0.00** | all providers free-tier (Groq/Cerebras/Gemini, Serper free credits) |
| Cash cost per record | **$0.00** | $0 spend / any record count |

Cost is $0 by construction (free tiers only); throughput, not cash, is the binding
constraint (see `docs/DATA_HONEST_LIMITS.md`).

_Reviewer note:_ ______________________________________________________________

## Architecture notes — claim ↔ artifact map

Only what maps to a real file / log / branch is listed. Design rationale and
tier-logic are left blank for the reviewer.

| Component | Where it lives |
|---|---|
| Discovery sources (ADV / EDGAR / 990 / News / CIK / Wikidata) | `pipeline/discovery/*.py` |
| Candidate pool + source interleave | `pipeline/build_candidates.py` |
| Function proof + IS/operates-as gate | `pipeline/enrichment/function_proof.py`, `pipeline/ontology.py::establishes_fo_function` |
| Website finder (Serper, then browser) | `pipeline/enrichment/serper.py`, `pipeline/enrichment/render.py` |
| Reach recovery (Serper LinkedIn, mailto, direct phone) | `pipeline/enrichment/reach.py`, `pipeline/enrichment/contacts.py` |
| Multi-provider LLM round-robin | `rag/llm.py` |
| Validation + inclusion floor | `pipeline/validation/`, `pipeline/ontology.py` |
| Escalation (needs-human) | `pipeline/escalation.py`, `rag/escalation.py`, `data/state/needs_human.json` |
| Staleness engine | `pipeline/staleness.py` |
| Scheduled climb | `.github/workflows/climb.yml`, `pipeline/climb.py` |
| RAG agent + goals | `rag/agent.py`, `data/goals/` |
| Failure exhibit | `docs/FAILURES.md` |

_Reviewer note:_ ______________________________________________________________
