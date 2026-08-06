# Dataset self-report

Computed from `data/final/dataset.csv` by `python -m pipeline.report`. Re-run it against the committed file and the numbers match — these are not hand-maintained.

**Qualifying records:** 8

## Principal emails (by honest status)

| Measure | Count |
| --- | ---: |
| Verified personal (our SMTP mailbox check passed) | 0 |
| Inferred personal (provider/MX-only, not mailbox-confirmed) | 0 |
| Any principal email present | 0 |
| 200-verified-email gate | 200 |
| Shortfall to gate | 200 |

> Honest shortfall: 0 of 200 verified-personal emails. The gap is documented, not filled with pattern-built or unverified addresses.

## Source mix — records per discovery-source class

A record found by more than one source is counted under each class it came from, so these can sum to more than the record count.

| Discovery source class | Records |
| --- | ---: |
| SEC Form ADV (registered adviser roster) | 8 |

### Exact stored labels (each record counted once)

| discovery_source (as stored) | Records |
| --- | ---: |
| SEC Form ADV (registered adviser roster) | 8 |
