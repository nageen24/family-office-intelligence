# Methodology Summary

How the system found the family-office records, how it enriched them, how I
validated the output, which source classes supported which claims, and the blind
spots that remain. Written to reconcile with the delivered artifacts — the counts
here match `data/final/dataset.csv`.

## The two jobs, kept separate: discovery vs proof

The pipeline treats *finding a firm* and *proving facts about it* as different
jobs with different sources (per the assessment's sourcing rule).

**Discovery sources** (where a firm was first surfaced):
- **SEC CIK registry** (entity-name scan for "Family Office") — 38/50
- **SEC EDGAR full-text search** — 6/50
- **Google News RSS** (named family offices in the news) — 6/50

Additional discovery connectors are built and run into the candidate pool
(ProPublica Form 990 for hidden family foundations, OpenCorporates, Wikidata),
but few of their candidates cleared firm-level qualification, so they contribute
little to the final 50. **This is the file's main blind spot — see below.**

**Proof / enrichment sources** (used to establish or verify a fact):
- **SEC 13F `primary_doc.xml`** — principal signer name + title + phone, and the
  13F portfolio value (an AUM-class figure). Official filing → stamped FACT/HIGH.
- **SEC submissions JSON** (`data.sec.gov`) — business phone + address.
- **Website discovery + HTTP/MX verification** — website and domain reachability.
- **Google News** — recent dated signals.

## Firm-level qualification (Rule 2)

A record only counts toward the 50 if there is affirmative evidence the firm is a
family office — not merely a wealthy-client firm or a family-named entity. The
strongest evidence used: **a 13F institutional filer whose registered name is a
"Family Office."** Family offices are exempt from SEC *adviser* registration (the
Family Office Rule) but not from Form 13F, so a 13F filer named "… Family Office"
is a provably real, active family office. Firms we could not establish stay out of
the 50 and sit in the rejection log (215 rejected).

## Type labelling — deliberately conservative

Categories: **SFO / MFO / Unconfirmed.** Current split: **3 SFO, 2 MFO, 45
Unconfirmed.** Most firms are "Unconfirmed" because the 13F filing proves they are
a family office but does not prove single-vs-multi. Rather than guess (relabeling
is penalised), the type stays Unconfirmed and the RAG surfaces it in tiers
(confirmed / likely-by-name / unproven). Honest, but see blind spots.

## Cell-level verification (Rule 1)

Every high-value cell carries its basis in dedicated columns: `__source`,
`__method`, `__confidence`, `__epistemic` (fact / inference / speculation), and
`__asof` date. A cell we could not verify is left honestly blank, not guessed.
Where validation found a value invalid, the value was removed from the delivered
field (e.g. the AUM values inflated 1000x by a thousands/dollars misread were
corrected; undeliverable/placeholder values are not shipped).

## What the numbers are, honestly (delivered 50)

- principal_name 34 · principal_title 35 · principal_phone 44 · principal_email 8
- aum 35 · website 31 · recent_signal 17 · investing_thesis 3
- Contact reachability is strong (phone 44/50); email and current-signal coverage
  are the weakest value cells.

## Material blind spots that remain

1. **Source concentration.** 44/50 firms were discovered through SEC (CIK + EDGAR).
   Verification proves facts about the firms found; it cannot recover firms SEC
   never showed us. SEC-13F discovery structurally over-represents family offices
   large enough to hold >$100M in US equities and file — and under-represents the
   small, invisible single-family offices that are the highest-value prize. This is
   the file's biggest limitation, and I'm stating it plainly rather than hiding it.
2. **SFO thinness.** Only 3 confirmed SFOs, for the same reason — the invisible
   ones don't file 13F. The non-SEC discovery connectors were built to reach them
   but yielded few *provable* family offices in the time available.
3. **Principal email + LinkedIn** are thin (email 8/50, LinkedIn 0/50); 13F gives
   names and filer phone, not personal email/LinkedIn, which need a separate,
   slower enrichment pass.
4. **Signal freshness** — 17/50 carry a dated recent signal; the rest are static
   firm-and-contact records.
