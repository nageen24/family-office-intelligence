"""Answer layer: the agentic 2-LLM grounding control (candidate's decision).

Two separate LLM calls, per DECISIONS.md (2026-07-28):
  LLM-1 (Answerer)  drafts an answer from ONLY the retrieved records.
  LLM-2 (Validator) audits that draft against the same records and returns
                    APPROVE / REFINE / DECLINE — the user never sees an
                    unchecked answer.

A retrieval-score gate runs first (cheap decline before spending the LLMs).
This is a mechanical control, not a prompt promise: a second model with a narrow
adversarial mandate and the power to decline is what stops the system lying when
the evidence is thin — exactly the "qualify / limit / decline" the assessment
requires.
"""
from __future__ import annotations

import re
from functools import lru_cache

from rag.retrieve import retrieve, _client, COLLECTION, is_single_query, is_multi_query
from rag.llm import chat as _chat


@lru_cache(maxsize=1)
def corpus_size() -> int:
    """Total records in the dataset (not the retrieved slice)."""
    try:
        return int(_client().count(COLLECTION).count)
    except Exception:
        return 0

# Distinct user-facing states (assessment: success / empty / partial / failure),
# each rendered differently by the UI. `verdict` stays for the answer path.
EMPTY_MSG = ("Please type a question — for example, \"family offices in New York\" "
             "or \"which firms have a recent investment signal?\"")
DECLINE_MSG = ("I can't answer that confidently from the verified data we hold. "
               "Try rephrasing, or ask about a firm's type, location, AUM, or recent activity.")
NO_MATCH_MSG = ("No family office in our dataset matches that. Try a broader query, "
                "or ask about type, location, AUM, or recent activity.")
ERROR_MSG = ("Our answering service is momentarily unavailable — this is on our "
             "side, not your question. Please try again in a moment.")

ANSWERER_SYS = (
    "You are a family-office intelligence assistant for an investor-relations "
    "professional. The full dataset contains {total} verified family offices; "
    "for each question you are shown only the most relevant records, NOT all "
    "{total}. So never state or imply that the dataset only contains the number "
    "of records shown to you — if asked how many family offices exist in total, "
    "the answer is {total}. Answer ONLY from the records provided. If a specific "
    "fact is not present in the records, say it is not available — never invent "
    "names, emails, phone numbers, or figures. FORMAT for easy reading, never a "
    "run-on paragraph: when giving ONE firm's details, start with a short sentence "
    "naming the firm, then put each fact on its OWN line as a bullet starting with "
    "'- ' and a label, e.g.\n"
    "- Location: ...\n- Type: ...\n- AUM: ...\n- Contact: ...\n- Phone: ...\n"
    "- Email: ...\n- Website: ...\n"
    "(only include lines you have data for). When listing MULTIPLE firms, use a "
    "numbered list, one firm per line. Put every list item on its own line. Do NOT "
    "use markdown tables, pipe characters, or ** bold ** symbols. Do not expose "
    "internal field names or jargon.")

def looks_likely_multi(name: str) -> bool:
    """A name-evidence signal that an Unconfirmed firm is probably multi-family:
    the name is plural ("... Family Offices") or literally says multi-family. It's
    the same naming logic that let us confirm 'Covenant Multifamily Offices' — but
    a notch weaker (plural could be stylistic), so these go in a separate 'likely'
    tier, never asserted as confirmed.
    """
    n = name.lower()
    return ("multifamily" in n or "multi-family" in n
            or re.search(r"family offices\b", n) is not None)


def _numbered(names: list) -> list:
    return [f"{i}. {n}" for i, n in enumerate(names, 1)]


def _format_type_answer(kind: str, confirmed: list, likely: list,
                        unconfirmed: list) -> str:
    """The user's graded firm-type answer (DECISIONS.md 2026-07-28), built
    deterministically from the records, strongest evidence first:
      1. confirmed as the asked type,
      2. (multi only) very likely by name evidence — plural "Family Offices" /
         "Multifamily" — but not formally confirmed,
      3. verified firms whose single-vs-multi label simply isn't proven yet.
    Tiers with no members are omitted. No LLM: can't hallucinate, can't time out.
    """
    singular = kind[:-1]  # "multi-family offices" -> "multi-family office"
    lines = []
    if confirmed:
        lines.append(f"Confirmed {kind}:")
        lines += _numbered(confirmed)
    else:
        lines.append(f"No firm in the dataset is yet confirmed as a {singular}.")
    if likely:
        lines += ["", "—",
                  f"Very likely {kind}, on name evidence — each is named in the "
                  f"plural (\"Family Offices\" / \"Multifamily\"), which signals it "
                  f"serves multiple client families — though not formally confirmed:"]
        lines += _numbered(likely)
    if unconfirmed:
        lines += ["", "—",
                  "Verified firms whose type (single vs multi family) simply isn't "
                  "confirmed yet — the records are correct and verified, only the "
                  "single/multi label is missing:"]
        lines += _numbered(unconfirmed)
    return "\n".join(lines)


VALIDATOR_SYS = (
    "You audit a draft answer against the source records it was based on. The "
    "full dataset contains {total} verified family offices (a known fact you may "
    "accept), and the answerer was shown only the most relevant subset — so do "
    "NOT decline an answer merely for stating the dataset has {total} family "
    "offices, or for not listing all of them. Be strict about everything else. "
    "Reply with exactly one of:\n"
    "  'APPROVE' — every claim in the draft is directly supported by the records.\n"
    "  'REFINE: <corrected answer>' — the draft is mostly right but overstates or "
    "adds something unsupported; give the corrected, fully-supported answer.\n"
    "  'DECLINE: <reason>' — the records do not support a confident answer "
    "(especially any specific contact detail, name, or figure that is not in the records).")


def _context(hits) -> str:
    return "\n".join(f"- {h.get('blurb', '')}" for h in hits)


def _compact_context(hits) -> str:
    """A one-line-per-firm view for whole-corpus questions (list / type / rank).

    Those pull 47-50 records; the full contact blurbs would push two sequential
    LLM calls past the serverless time limit. A list/rank answer only needs the
    name, type and the ranked field (AUM / location), so we hand the LLM that —
    the rich blurb stays for the small, detail-seeking queries.
    """
    lines = []
    for h in hits:
        parts = [h.get("firm_name", ""), f"type={h.get('firm_type', 'Unconfirmed')}"]
        if h.get("location"):
            parts.append(f"location={h['location']}")
        if h.get("aum"):
            parts.append(f"AUM={h['aum']}")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def answer(query: str) -> dict:
    """Return {"text", "status", "verdict", "sources"}.

    status is the coarse state the UI renders on:
      empty      — no/blank question
      no_match   — retrieval found nothing at all
      declined   — evidence too weak / validator declined / off-topic
      answered   — a grounded answer (verdict = approved|refined)
      error      — our services failed (never the user's fault)
    """
    if not query or not query.strip():
        return {"text": EMPTY_MSG, "status": "empty", "verdict": "declined", "sources": []}

    # Enumerate intent ("list all", "name every", "all 50") needs the whole
    # corpus in context, not just the top-k, or it can only list a slice.
    ql = query.lower()
    enumerate_all = any(p in ql for p in
                        ("all ", "list every", "name all", "every family office",
                         "show all", "name every", "list all"))
    # Superlative / aggregate ("largest AUM", "how many in NY", "rank by") can't be
    # answered from a semantic top-k slice — the true answer may sit outside it. The
    # corpus is small, so hand the LLM every record and let it compare / count.
    aggregate = any(p in ql for p in
                    ("largest", "biggest", "highest", "smallest", "lowest",
                     "most ", "top ", "rank", "how many", "count", "average",
                     "compare", "total aum", "sort"))
    # A type question pulls the confirmed firms of that type + all Unconfirmed
    # ones (retrieve.py widens the filter), so it needs the whole corpus in view.
    single_q, multi_q = is_single_query(ql), is_multi_query(ql)
    type_query = single_q or multi_q
    k = (corpus_size() if ((enumerate_all or aggregate or type_query) and corpus_size())
         else 8)

    try:
        r = retrieve(query, k=k)
    except Exception:
        return {"text": ERROR_MSG, "status": "error", "verdict": "declined", "sources": []}

    if not r["hits"]:
        return {"text": NO_MATCH_MSG, "status": "no_match", "verdict": "declined", "sources": []}
    if r["gated"]:
        return {"text": DECLINE_MSG, "status": "declined", "verdict": "declined", "sources": []}

    whole_corpus = enumerate_all or aggregate or type_query
    sources = [h.get("firm_name") for h in r["hits"]]

    # A pure firm-type question is a deterministic structured operation: the two
    # sections are exactly "records of the asked type" and "records typed
    # Unconfirmed". Formatting them directly (no LLM) is instant, can't
    # hallucinate, and dodges the serverless timeout that regenerating a 45-firm
    # list through a free-tier LLM caused. (If AUM/ranking is also asked, fall
    # through to the LLM path so the ranking is actually computed.)
    if type_query and not aggregate:
        code = "MFO" if multi_q else "SFO"
        kind = "multi-family offices" if multi_q else "single-family offices"
        confirmed = [h.get("firm_name") for h in r["hits"] if h.get("firm_type") == code]
        unconf = [h.get("firm_name") for h in r["hits"]
                  if h.get("firm_type") == "Unconfirmed"]
        # Multi-family gets a middle tier: Unconfirmed firms whose plural name is
        # name-evidence they're likely MFO. Single-family has no equivalent name
        # signal (a surname office can still be multi), so its middle tier is empty.
        if multi_q:
            likely = [n for n in unconf if looks_likely_multi(n)]
            rest = [n for n in unconf if not looks_likely_multi(n)]
        else:
            likely, rest = [], unconf
        return {"text": _format_type_answer(kind, confirmed, likely, rest),
                "status": "answered", "verdict": "approved", "sources": sources}

    ctx = _compact_context(r["hits"]) if whole_corpus else _context(r["hits"])
    answerer_sys = ANSWERER_SYS.format(total=corpus_size() or "the")
    validator_sys = VALIDATOR_SYS.format(total=corpus_size() or "the")

    try:
        draft = _chat(answerer_sys, f"Records:\n{ctx}\n\nQuestion: {query}")
        if whole_corpus:
            # A whole-corpus list / rank / count is a mechanical read of the
            # structured fields we supplied. The adversarial validator adds latency
            # without protection here, but the DETERMINISTIC release gate still
            # recomputes the counts from the CSV and blocks a wrong total.
            return _released(draft, "approved", sources)
        verdict = _chat(validator_sys,
                        f"Records:\n{ctx}\n\nQuestion: {query}\n\nDraft answer: {draft}")
    except Exception:
        # LLM/network failure is OUR problem — say so, don't fake a decline.
        return {"text": ERROR_MSG, "status": "error", "verdict": "declined", "sources": []}

    v = verdict.strip()
    up = v.upper()
    if up.startswith("APPROVE"):
        return _released(draft, "approved", sources)
    if up.startswith("REFINE"):
        refined = v.split(":", 1)[1].strip() if ":" in v else draft
        return _released(refined, "refined", sources)
    return {"text": DECLINE_MSG, "status": "declined", "verdict": "declined", "sources": sources}


def _released(text: str, verdict: str, sources: list) -> dict:
    """Deterministic release gate: plain code recomputes the corpus counts from the
    CSV and blocks the answer if the LLM's numbers don't match (not a prompt promise)."""
    try:
        from rag.release_gate import recompute_truth, release_gate
        from rag.structured import load_records
        gate = release_gate(text, recompute_truth(load_records()))
    except Exception:
        gate = {"ok": True, "reason": None}
    if not gate["ok"]:
        return {"text": DECLINE_MSG, "status": "declined", "verdict": "declined",
                "sources": sources, "gate_blocked": gate["reason"]}
    return {"text": text, "status": "answered", "verdict": verdict, "sources": sources}
