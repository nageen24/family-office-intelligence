# Dataset: what it holds, and the honest $0 ceiling

This documents, factually, what the Stage-2 dataset contains and why — so nothing
is over-claimed. It reflects the pipeline that produces `data/final/dataset.csv`.

## What every DELIVERED record has proven

A record is delivered (counts) only when the code proves ALL of:
- **Exists** — SEC CIK / own website / registry location / named principal.
- **Functions as a family office** — a VERBATIM sentence from the firm's OWN
  site/filing (or a SEC family-office exemption) that an LLM quoted and code then
  confirmed literally appears on the page. Name, 13F, press, and registry class do
  **not** qualify a firm.
- **Type** — SFO / MFO / FO-type-unknown, from an own-source quote.
- **Entity-coherent** — every value belongs to the same firm (wrong-entity values
  are quarantined, not shipped).
- **A personal reach route** — a named principal PLUS their own email, own direct
  phone, or own LinkedIn. Firm switchboards and info@ inboxes never count.

## Per-record transparency labels (buyer sees exactly what's there)

- `category` — SFO / MFO / FO-type-unknown
- `is_commercial` — has decision-maker + focus/mandate + reachable route + dated signal
- `has_investing_focus` — a verbatim investing/mandate statement from the firm's site
- `has_recent_signal` — a dated "why-now" news item
- per-cell `__status` (verified / inferred / unresolved / quarantined) and
  `__route` (personal / firm-level)

## Discovery sources (a real mix, each recorded per record)

SEC Form ADV roster (backbone, own websites), SEC EDGAR full-text, ProPublica 990,
Google News, SEC CIK registry, Wikidata. OpenCorporates is unavailable on the free
tier (401). Only ADV and Wikidata supply websites directly; the name-only sources
need website discovery to become qualifiable.

## The honest ceiling (why not 500 fully-rich records at $0)

Family offices are private by design. Measured on live runs:
- Function/type proof is available for most firms whose site is fetchable.
- **Personal reach (email / LinkedIn / direct phone) is rare** — the binding limit.
  Personal emails are ≈0 (not published); LinkedIn is present on a minority of team
  pages; direct phones almost never. This caps how many records carry a real way to
  reach the person.
- Investing-focus statements are sparse; many firms state none in a clean sentence.
- ~40% of stored website URLs are stale/bot-blocked/JS-only and fetch little.

Net: a complete, commercial-grade, reachable record is achievable for only a
fraction of firms at $0. The dataset therefore ships the **verified records the
public record honestly supports** — real intelligence where firms publish it,
honest blanks where they don't — rather than a padded count.

## Reach-finding: what was tried, and the wall (audit trail)

Personal reach (the binding limit) was attacked directly before any provider was
added. Every free path is blocked or empty from this environment:

- **Static site LinkedIn** — works for only ~22% of function-proven firms (the
  rest don't link their principals' profiles).
- **Bing search via a real browser** — result URLs are obfuscated behind
  redirect encoding; 0 extractable LinkedIn profiles.
- **DuckDuckGo** — scripted requests return HTTP 202 (bot-block); via a real
  browser (lite/, html/, duckduckgo.com/html) it serves an anomaly/bot page with
  0 results. Blocked both ways from this IP.
- **Full JS render** of firms' own team pages — returns content but 0 LinkedIn
  profiles (Seneschal 9k / TFO 7.7k / Colony 4.9k chars, all zero); slow and
  occasionally hangs.

**Decision (recorded): add Apollo on the free tier as a contact-data source**,
because the reach data exists only behind a provider. Apollo enters like any other
source — through the pipeline, with our OWN validation (the returned profile must
match the named person AND the current firm) and HONEST labels: a provider-returned
value is `inferred`, never `verified`. An Apollo email counts as a personal reach
route but does NOT count toward the 200 *verified* emails unless it also passes our
own SMTP mailbox check. Scarce free-tier email credits are spent only on the
strongest records; LinkedIn (which recovers the reach gate) is fetched first.

**Apollo free-tier result (tested live, recorded):** Apollo's People API is
**paid-only**. All three people endpoints return `403 API_INACCESSIBLE` on the free
plan — `people/match`, `mixed_people/search`, `people/search`
("*not included in your Free plan… all paid plans include full API access*"). So
Apollo cannot fill reach at $0. The integration (`pipeline/enrichment/apollo.py`) is
built, tested, and ready — own name+firm validation, honest `inferred` labels,
email-credit discipline — and activates the moment a PAID Apollo key is supplied;
it is a graceful no-op otherwise. No free contact-data API examined provides enough
to move the ~22% reach wall (Hunter's free plan is ~25 lookups/mo, negligible).
**Conclusion: reaching 500-with-reach requires a paid data plan; at strict $0 the
honest ceiling stands at ~130–250 genuinely-reachable records.**

## Verified personal emails — the free stack, and the honest count

The full free email stack is in place:
1. **Scrape `mailto:` personal emails** from the firm's own team/contact pages
   (pulled from the raw hrefs, which tag-stripping used to drop).
2. **Apollo free-tier credits on the strongest records only** (graceful no-op;
   People API is paid-only, see above — recovers ~0 at $0).
3. **Free MX + SMTP RCPT verifier** promotes a real address to `verified`.

Every scraped/provider address enters **`inferred`** and becomes **`verified`**
only if our own SMTP mailbox check confirms it. Nothing is pattern-guessed.

**Measured honestly (474 firms attempted): 0 verified personal emails** — 200
short of the gate. Why, factually:
- Personal emails are almost never published on firm sites (privacy by design);
  across the run only 1 firm exposed a same-domain personal address at all.
- That one is `inferred`, not `verified`: SMTP RCPT on port 25 is blocked/greylisted
  from this environment (and many providers accept-all), so the mailbox can't be
  positively confirmed — we do **not** upgrade an unconfirmed probe to `verified`.
- Apollo (the provider path to emails) is paid-only on the free tier.

This is the documented miss: at strict $0 the verified-personal-email count is far
under 200, and we report it as such rather than fabricate or pattern-build addresses
to hit the number. The stack activates and the count rises the moment a residential/
paid SMTP path or a paid contact-data key is supplied.
