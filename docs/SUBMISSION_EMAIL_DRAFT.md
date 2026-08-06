# SUBMISSION EMAIL — DRAFT ONLY, DO NOT SEND

> Fill the two `[[...]]` placeholders (live URLs) and write the unique-value
> paragraph yourself where marked, then send manually. Wording is deliberately
> plain and claims only what the files support.

---

**Subject:** Family Office Intelligence — Stage 2 submission

Hi [[recipient]],

Here is the Stage 2 submission. Everything is in the repo and reproducible from
the committed files.

**Live:**
- App: [[LIVE_APP_URL]]
- Repo: [[LIVE_REPO_URL]]

**What it does (one line each):**
- Discovers candidate firms from six sources — SEC Form ADV, SEC EDGAR, ProPublica 990, Google News, SEC CIK, Wikidata (`pipeline/discovery/`).
- Proves family-office function only from a firm's own site stating it IS / operates as a family office — code-verified quote, not a name or a services line (`pipeline/ontology.py`).
- Finds websites for name-only firms via Serper and recovers reach (LinkedIn, mailto, direct phone) on the free tier only (`pipeline/enrichment/`).
- Runs LLM extraction across free providers (Groq ×2, Cerebras, Gemini) with per-provider health reporting (`rag/llm.py`).
- Validates each record against an inclusion floor and withholds anything that fails, with the reason kept for audit (`pipeline/validation/`).
- Escalates genuinely ambiguous records to a human queue instead of deciding (`pipeline/escalation.py`).
- Re-checks records across runs and demotes/refreshes them on evidence (`pipeline/staleness.py`).
- Runs unattended on a 3-hour schedule, committing state back to the repo (`.github/workflows/climb.yml`).

**Honest numbers (recomputed in `docs/RECONCILIATION.md`):**
- 2 qualifying records (both SEC Form ADV; 1 MFO, 1 FO-type-unknown); 7 firms function-proven; 474 attempted.
- 0 verified personal emails against the 200 target — documented as a miss in `docs/DATA_HONEST_LIMITS.md`, not padded.
- 15 scheduled runs over 59 hours; $0 cash cost (free tiers only).

**Supporting docs:**
- `docs/RECONCILIATION.md` — every number, recomputed from the files.
- `docs/DATA_HONEST_LIMITS.md` — the $0 ceiling and what is genuinely blocked.
- `docs/FAILURES.md` — real failures, causes, and fixes.
- `docs/OPERATING_WINDOW.md` — 48h+ operation, an induced dependency failure, a cross-run staleness catch.
- `data/goals/` — the evaluation goals with manual-retrieval output, agent output, and raw run logs.

**What is deliberately small:** the qualifying count is low because the proof and
reach bars are strict and the budget is $0. The pipeline ships only what the
public record honestly supports rather than a padded number; the constraints are
documented above.

[[ONE-PARAGRAPH UNIQUE-VALUE STATEMENT — you write this]]

Thanks,
[[your name]]

---
_Draft ends. Nothing sent._
