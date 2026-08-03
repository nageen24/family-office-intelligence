# Status of files in data/final/

**As of Stage 2, Phase 1 (S8 requalification).**

## `dataset.csv`, `dataset.xlsx`, `extended_qualified.csv` — STALE (Stage 1)

These are the Stage-1 deliverables. They were produced under the earlier
standard and have **not** been re-qualified under the corrected Stage-2 ontology.
They are retained only so the retrieval demo keeps working during the build.
**Do not treat them as current Stage-2 output.** Phase 2 repopulates them with
records that meet the new standard (500 target).

## `rejection_log.csv` — STALE (Stage 1)

The Stage-1 rejection log.

## `stage1_requalification.csv` — CURRENT (S8 audit)

The Stage-1 enriched pool (281 firms) re-run through the corrected Stage-2
engine. Result under the locked standard:

- **0 of 281 qualify.** All are relabeled **Unresolved-Quarantine**.
- **0** carry an own-source FO-function quote (strict Proof B: function is
  proven only by the firm's own filing/site statement or a SEC family-office
  exemption; name / 13F / press / registry do not prove function).

This is an audit surface: each row shows the withheld values and the reason.
It is the honest requalification of the Stage-1 file, not a customer deliverable.

Regenerate with: `python -m pipeline.requalify_stage1`
