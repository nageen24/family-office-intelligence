# Full Validation Chains — 3 Records

For three delivered records: discovery source → extraction method → enrichment
steps → validation logic → confidence assessment → exact sources. All three are
verifiable from public links; nothing here is hand-entered.

---

## 1. Duquesne Family Office LLC

- **Discovery source:** SEC EDGAR full-text search (surfaced the entity as a 13F
  filer named "Family Office").
- **Extraction:** entity name + CIK (0001536411) captured from the EDGAR listing.
- **Enrichment steps:**
  - 13F `primary_doc.xml` → signature block → **Sue Meng, General Counsel**;
    portfolio value → **$3.38B**.
    Source: https://www.sec.gov/Archives/edgar/data/1536411/000153641126000004/primary_doc.xml
  - SEC submissions JSON (CIK 0001536411) → **phone (212) 830-6500**, HQ 40 West
    57th Street, 25th Floor, New York, NY.
  - Google News → recent signal: "Duquesne Family Office Ups Micron Technology
    Stake by 23,400 Shares" (The Globe and Mail).
- **Validation logic:**
  - *Firm (Rule 2):* qualifies — an institutional 13F filer named "Duquesne Family
    Office LLC" is affirmative evidence of a real, active family office.
  - *Type:* left **Unconfirmed** — 13F proves it's an FO, not single-vs-multi. Not
    guessed.
  - *AUM:* raw 13F total read as dollars vs thousands via the $100M-floor +
    average-position check → $3.38B (avg ~$48M/position, plausible).
- **Confidence:** principal name/title and AUM = FACT / HIGH (official filing);
  type = honest unknown.
- **Note:** principal email left blank — not available from these sources, not
  invented.

---

## 2. Stenger Family Office, Llc

- **Discovery source:** SEC CIK registry (entity-name scan), CIK 0002056106.
- **Extraction:** entity name + CIK from the registry.
- **Enrichment steps:**
  - 13F `primary_doc.xml` → signature block → **Julia Patricia Foran, VP
    Operations**; portfolio value → **$629.4M**.
    Source: https://www.sec.gov/Archives/edgar/data/2056106/000208585326000698/primary_doc.xml
  - SEC submissions JSON → **phone 630-912-8295**, HQ Naperville Financial Center,
    400 East Diehl Rd, Suite 550, Naperville, IL.
  - Website discovery + verification → **https://stengerfamilyoffice.com** (HTTP/MX
    checked live).
  - Contact email → **nick.stenger@stengerfamilyoffice.com** (domain verified).
  - Google News → signal: "Stenger Family Office LLC Has $28.84 Million Holdings in
    Microsoft" (MarketBeat).
- **Validation logic:** Rule 2 satisfied (named 13F filer). Website confirmed
  resolving; email domain matches the verified website.
- **Confidence:** name/title/phone/AUM = FACT / HIGH; website = verified;
  reachability score **80** (has phone + email + recent signal — one of the most
  actionable records in the file).

---

## 3. Callan Family Office, Llc

- **Discovery source:** SEC CIK registry (entity-name scan), CIK 0001938970.
- **Extraction:** entity name + CIK.
- **Enrichment steps:**
  - 13F `primary_doc.xml` → signature block → **John Ginter, CEO and CCO**;
    portfolio value → **$4.41B**.
    Source: https://www.sec.gov/Archives/edgar/data/1938970/000193897026000003/primary_doc.xml
  - SEC submissions JSON → **phone (267) 250-2036**, HQ 201 King of Prussia Road,
    Suite 650, Radnor, PA.
  - Website discovery + verification → **https://callanfamilyoffice.com**.
- **Validation logic:** Rule 2 satisfied (named 13F filer). Type Unconfirmed
  (13F does not resolve single-vs-multi). This is a case worth noting: Callan is
  *very likely* a multi-family office by name and profile, but I did not have a
  firm's-own-statement to confirm it, so the delivered type stays Unconfirmed and
  the RAG surfaces it in the "likely" tier rather than asserting MFO.
- **Confidence:** name/title/phone/AUM = FACT / HIGH; website verified; no recent
  dated signal found, so that cell is honestly blank (lower reachability score 25).

---

**Common thread:** the firm qualifies on official 13F evidence; the high-value
cells (principal, phone, AUM) come from the filing and are labelled FACT/HIGH with
the exact URL; unresolved cells (email for Duquesne/Callan, signal for Callan,
single-vs-multi type for all three) are left honestly blank rather than guessed.
