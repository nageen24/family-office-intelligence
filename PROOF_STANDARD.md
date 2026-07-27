# Proof Standard — what a firm and a cell must prove before it ships

This is the bar my pipeline holds every record to. It exists because the
assessment has two *separate* rules, and I wanted mine written down before I
built, not rationalized after.

## Rule 2 — the firm itself (strict)

A firm is only counted as a family office when there is **affirmative evidence**
of it. Serving wealthy clients, having "family" in the name, or appearing in a
family-office list is **not** enough.

I use three categories and require this evidence for each:

- **SFO (single-family office):** language/structure showing it serves ONE
  family and does not solicit external clients — e.g. "single family office",
  "our family", "not accepting new clients", a Form ADV showing ~1 client, or a
  claimed SEC family-office exemption. Stored in `type_evidence`.

  Two additional SFO evidence bases I adopted during the build, both written
  down BEFORE applying them:

  1. **Official 13F under a family-office name.** Family offices are exempt
     from SEC adviser registration but NOT from Form 13F (mandatory above
     $100M in US equities). A firm that files 13F under a "Family Office" name
     and shows no client-serving language anywhere is a real, active family
     office on federal record — my strongest SFO basis (fact/high).
  2. **Press-possessive of one named individual.** A headline attributing the
     office to a single named person — "Jeff Bezos' family office", "the
     family office of Ray Dalio" — is affirmative single-family evidence: an
     office belonging to one person serves one family by definition. Labeled
     inference/medium, with the exact headline + URL stored as the evidence.
     The rule fires ONLY on a person-name possessive; generic names
     ("Singapore Family Office", "Modern Family Office") never qualify this
     way. I hand spot-check a sample of these upgrades, and the assessment
     explicitly permits manual spot-checks.
- **MFO (multi-family office):** evidence it serves MULTIPLE families/clients —
  published services, fee schedule, "become a client"/onboarding, many ADV
  clients.
- **Unconfirmed:** it looks like an FO but the evidence can't separate SFO from
  MFO, or can't confirm it's an FO at all. **I label this honestly rather than
  guess.** Relabeling an MFO/advisor as an SFO to inflate value is the worst
  error in this domain, so I never do it.

A firm that reaches only "no affirmative family-office evidence" is **Rejected**
and routed to the rejection log — it does not count toward the 50.

## Rule 1 — individual cells

Every high-value cell (email, phone, LinkedIn, AUM, thesis, signal) carries:
`source` · `method` · `confidence (H/M/L)` · `epistemic (fact/inference/speculation)` · `as-of date`.

- **Email:** MX record check (free); optional Hunter free-tier deliverability.
  A domain with no MX, or a Hunter "undeliverable/invalid", is **removed from the
  contact field** and the reason is kept as the cell's method. MX-only passes are
  marked *inference / medium* because MX proves the domain accepts mail, not that
  the specific mailbox exists.
- **Phone / others:** kept only with a source; format-checked; low confidence
  when scraped from a single page without a second source.
- **Website:** every scripted search engine IP-blocks this environment (tested
  seven; Bing returned a Cloudflare bot-challenge), so candidate sites were
  found via Bing rendered in a **real browser**, then **verified in code**
  before being trusted: the candidate domain is fetched directly and accepted
  only if the firm's own distinctive name token *and* family-office context
  appear on the page, or the domain itself proves it (e.g.
  `biltmorefamilyoffice.com`). This is why wrong-company collisions
  (Duquesne→finnotes, Looper→the film site, Genspring→truist) were rejected,
  not shipped. Method recorded on the cell: "Bing-found in a real browser,
  verified by direct-fetch firm-name + family-office match."
- **Email:** scraped only from a **verified** firm site, restricted to the
  site's own registrable domain (a font vendor's address on the page is not the
  firm's email), placeholders filtered (`user@domain.com`), then **MX-checked**
  in validation — a domain with no mail server is dropped from the record.

## Honest blank over fake (the rule I refuse to break)

When a value can't be confirmed, the cell is left **blank and marked "could not
verify"** — never filled with a guess. This is a deliberate choice, and I want
the reason on record because it reflects the limits of a $0, ToS-respecting build:

- Free email checkers **cannot** confirm mailboxes on catch-all domains (the
  server accepts everything) — those stay medium/blank, not "verified".
- Firm-type is a **heuristic** from public text; ambiguous cases are Unconfirmed,
  and I spot-check a sample by hand.
- The most genuine SFOs often have **no website and no digital footprint** — so
  the highest-value records will carry honest blanks on contact cells by design.

A guessed value dressed up as "verified" would be disqualifying and, more to the
point, worthless to a customer. An honest blank is candor. I would rather ship a
smaller file of records I can stand behind than a full file I can't.
