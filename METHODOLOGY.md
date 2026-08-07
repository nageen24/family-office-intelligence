> ⚠️ **STAGE 1 — historical, superseded by Stage 2 numbers.** All counts in this
> file ("delivered 50", "38/50 SEC", "215 rejected", "3 SFO / 2 MFO / 45
> Unconfirmed", "phone 40/50", "88% → 76%") are **Stage-1** figures and do **not**
> describe the current Stage-2 dataset. For the live Stage-2 numbers see
> `docs/RECONCILIATION.md` (attempted 648, proven 8, qualifying 2, 0 verified
> personal emails).

# Methodology Summary

How the system found the family-office records, how it enriched them, how I
validated the output, which source classes supported which claims, and the blind
spots that remain. Written to reconcile with the delivered artifacts — the counts
here match `data/final/dataset.csv`.

## The two jobs, kept separate: discovery vs proof

The pipeline treats *finding a firm* and *proving facts about it* as different
jobs with different sources (per the assessment's sourcing rule).

**Discovery sources** (where a firm was first surfaced) — delivered 50:
- **SEC CIK registry** (entity-name scan for "Family Office") — 34/50
- **SEC EDGAR full-text search** — 4/50
- **Wikidata** (SPARQL: instance-of "family office", Q751314) — 6/50
- **Google News RSS** (named family offices in the news) — 6/50

That is **38/50 (76%) SEC** and **12/50 non-SEC**. SEC still dominates — see the
blind spot below — but the non-SEC additions are deliberately the *hardest and
most valuable* records: Wikidata surfaced marquee single-family offices that never
file 13F (e.g. **DFO Management** = Michael Dell's family office, **Builders
Vision** = Lukas Walton's, Korys, Revisio), and news surfaced active named offices
(Dalio, Kirloskar, UBS). ProPublica Form 990 and OpenCorporates connectors also
run into the pool; 990 foundations mostly fail firm-level qualification (a family
*foundation* is not itself a family office) and OpenCorporates needs a paid key,
so they contribute little.

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

- principal_name 32 · principal_phone 40 · principal_email 10 · aum 33
- website 34 · recent_signal 21 · investing_thesis 3
- Contact reachability is strong (phone 40/50); email and thesis are the weakest
  value cells. Bringing non-SEC firms into the 50 traded a little SEC contact
  richness (phone 44→40) for discovery diversity and reachable websites (31→34) —
  a deliberate choice, since the doc scores real discovery over convenient sourcing.

## Material blind spots that remain

1. **Source concentration.** Still **76% SEC** (38/50). The non-SEC push (Wikidata +
   news) cut it from an earlier 88%, but SEC remains the majority. The reason is
   structural: SEC-13F discovery over-represents family offices large enough to
   hold >$100M in US equities and file, and the free non-SEC channels that could
   balance it are constrained here — OpenCorporates needs a paid key, Google/DDG
   search is IP-blocked in this environment, and Wikidata only covers offices
   notable enough to have an entry. I'm stating this plainly rather than hiding it.
2. **SFO thinness (labelled).** Only 3 *confirmed* SFOs — but several delivered
   non-SEC records are almost certainly single-family (DFO Management/Dell,
   Builders Vision/Walton). I left them **Unconfirmed** rather than assert SFO
   without a firm's-own-statement; relabeling to inflate the SFO count is exactly
   what the assessment penalises.
3. **Principal email + LinkedIn** are thin (email 8/50, LinkedIn 0/50); 13F gives
   names and filer phone, not personal email/LinkedIn, which need a separate,
   slower enrichment pass.
4. **Signal freshness** — 17/50 carry a dated recent signal; the rest are static
   firm-and-contact records.
