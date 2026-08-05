"""Dataset self-report: figures computed FROM the file, source classes split."""
import pandas as pd

from pipeline.report import compute, render_markdown


def _write(tmp_path, rows):
    p = tmp_path / "dataset.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return str(p)


def test_email_counts_by_status_and_route(tmp_path):
    p = _write(tmp_path, [
        {"discovery_source": "SEC Form ADV",
         "principal_email": "a@x.com", "principal_email__status": "verified",
         "principal_email__route": "personal"},
        {"discovery_source": "SEC Form ADV",
         "principal_email": "b@y.com", "principal_email__status": "inferred",
         "principal_email__route": "personal"},
        {"discovery_source": "SEC Form ADV",
         "principal_email": None, "principal_email__status": "unresolved",
         "principal_email__route": None},
    ])
    s = compute(p)
    assert s["records"] == 3
    assert s["emails"]["verified_personal"] == 1
    assert s["emails"]["inferred_personal"] == 1
    assert s["emails"]["any_email_present"] == 2
    assert s["emails"]["gate_shortfall"] == 200 - 1     # honest shortfall shown


def test_source_class_split_counts_each_class(tmp_path):
    p = _write(tmp_path, [
        {"discovery_source": "SEC EDGAR full-text search + SEC CIK registry (entity names)"},
        {"discovery_source": "SEC Form ADV (registered adviser roster)"},
        {"discovery_source": "SEC Form ADV (registered adviser roster)"},
    ])
    s = compute(p)
    by = s["source_mix_by_class"]
    assert by["SEC Form ADV (registered adviser roster)"] == 2
    assert by["SEC EDGAR full-text search"] == 1
    assert by["SEC CIK registry (entity names)"] == 1        # both classes counted
    # combined keeps the merged label as one record
    assert s["source_mix_combined"][
        "SEC EDGAR full-text search + SEC CIK registry (entity names)"] == 1


def test_markdown_matches_computed_numbers(tmp_path):
    p = _write(tmp_path, [
        {"discovery_source": "Wikidata (P31: family office)",
         "principal_email": "a@x.com", "principal_email__status": "verified",
         "principal_email__route": "personal"},
    ])
    s = compute(p)
    md = render_markdown(s, p)
    assert "**Qualifying records:** 1" in md
    assert "Wikidata (P31: family office)" in md
    assert "| Verified personal (our SMTP mailbox check passed) | 1 |" in md


def test_missing_file_is_reported_not_crashed(tmp_path):
    s = compute(str(tmp_path / "nope.csv"))
    assert s["records"] == 0 and "not found" in s["note"]
    assert "not found" in render_markdown(s, "nope.csv")
