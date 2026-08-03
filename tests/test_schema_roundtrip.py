"""Schema + io round-trip for the Stage-2 ontology fields.

Guards that a record can actually CARRY the S1-S3 outputs (category, the three
proofs with their stored source-quote, and per-cell status/route) and that they
survive the interim JSON save/load the pipeline uses between stages.
"""
import importlib

from pipeline.schema import CandidateFirm, Cell
from pipeline.ontology import FirmCategory, Status, RouteType


def _firm() -> CandidateFirm:
    f = CandidateFirm(firm_name="Doe Family Office", discovery_source="SEC EDGAR")
    f.category = FirmCategory.SFO
    f.proof_exists = "SEC CIK 0001234567"
    f.proof_function_source = "https://doefamilyoffice.com/about"
    f.proof_function_quote = "We are the single family office of the Doe family."
    f.proof_type_quote = "single family office of the Doe family"
    f.entity_coherent = True
    f.counts_toward_500 = True
    f.is_commercial = False
    f.principal_email = Cell(value="jane.doe@doefamilyoffice.com",
                             status=Status.VERIFIED, route=RouteType.PERSONAL)
    return f


def test_flat_row_exposes_ontology_columns():
    row = _firm().to_flat_row()
    assert row["category"] == "SFO"
    assert row["proof_function_quote"].startswith("We are the single family office")
    assert row["counts_toward_500"] is True
    assert row["principal_email__status"] == "verified"
    assert row["principal_email__route"] == "personal"


def test_save_load_preserves_ontology_fields(tmp_path, monkeypatch):
    import pipeline.io_utils as io
    monkeypatch.setattr(io, "INTERIM", str(tmp_path))
    io.save_pool([_firm()], "rt")
    loaded = io.load_pool("rt")
    assert len(loaded) == 1
    g = loaded[0]
    assert g.category is FirmCategory.SFO
    assert g.counts_toward_500 is True
    assert g.principal_email.status is Status.VERIFIED
    assert g.principal_email.route is RouteType.PERSONAL
