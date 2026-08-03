"""S11 — verified email = mailbox-confirmed (free SMTP RCPT), catch-all aware.

The locked bar: verified only when an SMTP RCPT probe says the mailbox is
deliverable on a NON-catch-all domain. Catch-all or an inconclusive/blocked probe
= inferred (MX proves the domain accepts mail, not the mailbox). Undeliverable or
no MX = quarantined (withheld). MX-lookup and the SMTP probe are injected so the
mapping is tested without network.
"""
from pipeline.schema import Cell
from pipeline.ontology import Status
from pipeline.validation.validate import verify_email

_MX_OK = lambda domain: True


def _run(value, probe_result):
    return verify_email(Cell(value=value), mx_lookup=_MX_OK,
                        probe=lambda email: probe_result)


def test_deliverable_non_catchall_is_verified():
    out = _run("jane.doe@firm.com", "deliverable")
    assert out.status is Status.VERIFIED
    assert out.value == "jane.doe@firm.com"


def test_catch_all_is_inferred():
    assert _run("jane.doe@firm.com", "catch_all").status is Status.INFERRED


def test_blocked_or_unknown_probe_is_inferred_not_verified():
    out = _run("jane.doe@firm.com", "unknown")
    assert out.status is Status.INFERRED          # SMTP blocked (e.g. MS365) -> honest inferred
    assert out.value == "jane.doe@firm.com"


def test_undeliverable_is_quarantined_and_withheld():
    out = _run("ghost@firm.com", "undeliverable")
    assert out.status is Status.QUARANTINED
    assert out.value is None
    assert out.quarantined_value == "ghost@firm.com"


def test_no_mx_is_quarantined():
    out = verify_email(Cell(value="x@nomx.tld"),
                       mx_lookup=lambda d: False, probe=lambda e: "deliverable")
    assert out.status is Status.QUARANTINED


def test_blank_is_unresolved():
    out = verify_email(Cell(), mx_lookup=_MX_OK, probe=lambda e: "deliverable")
    assert out.status is Status.UNRESOLVED
