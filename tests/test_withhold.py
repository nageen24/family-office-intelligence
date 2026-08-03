"""S5 — validation WITHHOLDS/quarantines failing values, never ships them tagged.

The Stage-1 defect (fix#5): a wrong value (DFO snow-crab signal) was tagged
low-confidence but still written to the customer CSV. The fix: a failing value
is removed from every customer surface and its status becomes `quarantined`; the
original is kept ONLY in an audit field that never ships (user decision:
audit-preserve). A value that was simply never found is `unresolved`, not
quarantined.
"""
from pipeline.schema import CandidateFirm, Cell
from pipeline.ontology import Status


def test_quarantine_withholds_value_into_audit_field():
    c = Cell(value="nick.stenger@firm.com", source="scrape")
    c.quarantine("names a different person than the listed principal")
    assert c.value is None                       # off the customer surface
    assert c.status is Status.QUARANTINED
    assert c.quarantined_value == "nick.stenger@firm.com"   # audit-only
    assert "different person" in c.quarantined_reason


def test_mark_unresolved_is_a_blank_not_a_quarantine():
    c = Cell()
    c.mark_unresolved()
    assert c.value is None
    assert c.status is Status.UNRESOLVED
    assert c.quarantined_value is None           # nothing was withheld


def test_customer_row_hides_quarantined_value_but_keeps_status():
    f = CandidateFirm(firm_name="X FO", discovery_source="SEC")
    f.principal_email = Cell(value="a@b.com")
    f.principal_email.quarantine("no MX record (undeliverable)")
    row = f.to_flat_row()                         # customer surface (default)
    assert row["principal_email"] is None
    assert row["principal_email__status"] == "quarantined"
    assert "principal_email__quarantined_value" not in row   # audit excluded


def test_audit_row_exposes_the_withheld_value():
    f = CandidateFirm(firm_name="X FO", discovery_source="SEC")
    f.principal_email = Cell(value="a@b.com")
    f.principal_email.quarantine("no MX record (undeliverable)")
    row = f.to_flat_row(audit=True)
    assert row["principal_email__quarantined_value"] == "a@b.com"
    assert "no MX" in row["principal_email__quarantined_reason"]


def test_verify_email_quarantines_invalid_syntax_with_audit_preserve():
    from pipeline.validation.validate import verify_email
    out = verify_email(Cell(value="not-an-email", source="scrape"))
    assert out.value is None
    assert out.status is Status.QUARANTINED
    assert out.quarantined_value == "not-an-email"
