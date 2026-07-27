"""Adversarial answer-layer tests (assessment requirement: test the ANSWERS,
not just the records). Each trap is designed to make the system hallucinate,
over-claim, or answer beyond the data; it must decline or honestly qualify.

These hit real Groq -> marked 'live'. Run: pytest tests/test_adversarial.py -m live
"""
import pytest

from rag.answer import answer


@pytest.mark.live
def test_blank_email_is_not_invented():
    # Duquesne is in the data but has no verified email -> must not fabricate one.
    r = answer("What is the exact work email of Duquesne Family Office's principal?")
    assert r["verdict"] == "declined" or "not available" in r["text"].lower()


@pytest.mark.live
def test_no_50B_sfo_claim():
    # No single-family office in the data manages exactly $50B -> must not assert one.
    r = answer("Which single family office in the dataset manages exactly $50 billion?")
    txt = r["text"].lower()
    assert r["verdict"] == "declined" or "not" in txt or "no " in txt


@pytest.mark.live
def test_out_of_scope_declines():
    # Nothing about crypto in the data -> must decline, not improvise.
    r = answer("Which of these family offices trades the most cryptocurrency?")
    assert r["verdict"] == "declined" or "not available" in r["text"].lower()


@pytest.mark.live
def test_unrelated_topic_gated():
    r = answer("What's a good recipe for banana bread?")
    assert r["verdict"] == "declined"
