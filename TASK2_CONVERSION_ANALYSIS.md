# Task 2 — Why a Family-Office-Intelligence SaaS Converts at 3%, and How I'd Fix It

## Where I'm starting from

3% is low for SaaS in general, but I don't think this is a "conversion tactics"
problem — and I think that's the trap in the question. The reflex answer is better
onboarding, a stronger paywall, trial nudges, PQL scoring, tiered pricing. It's
competent, and it's the same advice you'd give *any* data SaaS. That's probably
exactly why the off-the-shelf models failed here: they optimized a funnel without
first asking whether the funnel is the problem.

My read is that for this specific buyer, 3% is close to the *rational* result of a
product/buyer mismatch. So I'd fix the mismatch, not the funnel.

## The specific thing about this buyer

The customer for family-office intelligence is almost always someone **raising
capital** — a fund's IR/capital-raising person, or a GP. Their need is acute and
**episodic**, not continuous:

- They're raising a fund *now*. They need allocators to reach. Once they have the
  list and have worked it, the acute need is largely gone until the next raise,
  which can be 1–3 years away.
- What they actually want isn't "data." It's **a meeting with an allocator who
  writes a check.** The database is the means; the booked intro is the value.

If that's right, then a free user who signs up, pulls the family offices matching
their strategy, grabs the contacts, and leaves is **not a failed conversion. They
got what they needed inside the free window.** A big share of the 97% aren't
unconvinced — they're a one-time need that a subscription simply can't hold, and a
subscription trial is the wrong container for them.

## So "3%" is really three problems wearing one number

I'd want the data to confirm the split, but my hypothesis is the 97% is roughly:

1. **Wrong audience** — researchers, students, competitors, tire-kickers who were
   never going to pay. → fix is *qualification*, not conversion.
2. **Right audience, one-time need** — capital raisers who extracted value and
   left. → fix is either *price-capture the one-time value*, or *make the data
   expire* (below).
3. **Right audience, didn't trust it** — they saw the data, doubted the contacts
   were real/current, and wouldn't risk $X on a maybe. → fix is *prove accuracy
   in the free tier.*

Blended 3% hides all three, and the cheapest lever is different for each. I'd
refuse to prescribe a single fix until I could size them — segmenting paying vs
non-paying accounts by role and behaviour is the first thing I'd do.

## What I'd actually change (specific to this domain, in priority)

1. **Turn "the list" from a one-time asset into a decaying one.**
   Family-office intel goes stale fast — principals move, mandates change, a family
   office allocating last quarter is closed this quarter. So lead with **freshness
   and signals** as the product, not the static list: who *started* allocating this
   month, who changed their principal, who just had a liquidity event. A static
   list is bought once; a signal feed is a reason to *stay* subscribed, because last
   quarter's list is wrong this quarter. This attacks the one-and-done problem at
   the root instead of nudging around it.

2. **Make the free tier prove trust, not tease volume.**
   For this buyer the fear is "these contacts are garbage." So free should expose a
   *small number of records with the verification fully shown* — source, date
   confirmed, "email checked deliverable." Let them *feel* the data is real. Gate
   quantity and the contact details, not the proof. Here, trust is the paywall more
   than volume is. (This is the same verification discipline the Task 1 dataset is
   built on — it's a selling feature, not just an internal standard.)

3. **Add a paid one-time tier for the episodic buyer.**
   Not everyone wants a subscription, and that's fine — capture them anyway. A
   "current raise" credit pack (N verified allocator contacts matched to your
   strategy) monetizes the one-time need directly instead of losing it to the free
   tier. Some convert to subscription later once the freshness angle proves itself.

4. **Sales-assist on the signal that means "raising now" — not generic PQL.**
   The intent signal that matters here isn't "viewed pricing twice." It's *evidence
   of an active raise*: filtered by a specific fund strategy, pulled a lot of
   contacts quickly, checked pricing. That person is worth a human email offering a
   curated allocator shortlist — because a warm intro is what they're really buying,
   and at $500–$10k+ price points a 15-minute call converts this buyer far better
   than an upgrade button.

## What I'm unsure about, and would validate before betting a quarter on any of it

- **My whole thesis rests on the base being episodic capital-raisers.** If the real
  paying base is *service providers* (lawyers, wealth managers, fund admins selling
  *to* family offices), their need is continuous and the "one-time" story is wrong —
  then it genuinely is a more ordinary onboarding/pricing problem. I'd segment
  paying vs churned accounts by role *first*.
- I don't know the current price point or contract shape. If they only offer an
  annual plan, the fix may simply be a monthly / one-time entry point. If they
  already have that and still see 3%, the retention/one-and-done story is the real
  one.
- The "signals/freshness" play is only honest if the activity data can actually be
  kept current — and from building the Task 1 dataset, I know that's genuinely hard.
  If they can't source fresh signals reliably, they shouldn't promise them.

## The one bet

If I had to pick a single highest-impact move: **reposition from "a database of
family offices" to "a live feed of family offices that are allocating right now,"
and prove the data's accuracy inside the free tier.** That converts a one-time
list-pull into a recurring reason to pay, and it directly answers why this
particular buyer didn't trust the product enough to convert. Tiers, sales-assist,
and qualification are all downstream of getting that one thing right.

One framing I'd keep on the wall: MRR = qualified signups × conversion × ARPU ×
retention. Conversion is one of four terms. For a niche data business, charging the
*right* users more (ARPU) and keeping them (retention, via freshness) may move MRR
faster than converting marginal free users at all.
