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

from functools import lru_cache

from rag.retrieve import retrieve, _client, COLLECTION
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
    "names, emails, phone numbers, or figures. Reply in plain English sentences "
    "and, when listing multiple firms, a simple numbered list — do NOT use "
    "markdown tables, pipe characters, or ** bold ** symbols. Do not expose "
    "internal field names or jargon.")

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
    k = corpus_size() if ((enumerate_all or aggregate) and corpus_size()) else 8

    try:
        r = retrieve(query, k=k)
    except Exception:
        return {"text": ERROR_MSG, "status": "error", "verdict": "declined", "sources": []}

    if not r["hits"]:
        return {"text": NO_MATCH_MSG, "status": "no_match", "verdict": "declined", "sources": []}
    if r["gated"]:
        return {"text": DECLINE_MSG, "status": "declined", "verdict": "declined", "sources": []}

    ctx = _context(r["hits"])
    sources = [h.get("firm_name") for h in r["hits"]]
    answerer_sys = ANSWERER_SYS.format(total=corpus_size() or "the")

    try:
        draft = _chat(answerer_sys, f"Records:\n{ctx}\n\nQuestion: {query}")
        verdict = _chat(VALIDATOR_SYS.format(total=corpus_size() or "the"),
                        f"Records:\n{ctx}\n\nQuestion: {query}\n\nDraft answer: {draft}")
    except Exception:
        # LLM/network failure is OUR problem — say so, don't fake a decline.
        return {"text": ERROR_MSG, "status": "error", "verdict": "declined", "sources": []}

    v = verdict.strip()
    up = v.upper()
    if up.startswith("APPROVE"):
        return {"text": draft, "status": "answered", "verdict": "approved", "sources": sources}
    if up.startswith("REFINE"):
        refined = v.split(":", 1)[1].strip() if ":" in v else draft
        return {"text": refined, "status": "answered", "verdict": "refined", "sources": sources}
    return {"text": DECLINE_MSG, "status": "declined", "verdict": "declined", "sources": sources}
