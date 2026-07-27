from rag.ingest import record_to_blurb, build_metadata

ROW = {
    "firm_name": "Duquesne Family Office LLC", "firm_type": "Unconfirmed",
    "aum": "$3.38B (13F portfolio value)", "principal_title": "General Counsel",
    "principal_name": "", "principal_phone": "212-830-6500",
    "hq_location": "NEW YORK, NY", "recent_signal": "", "website": "",
    "principal_email": "", "investing_thesis": "",
}


def test_blurb_mentions_key_facts():
    b = record_to_blurb(ROW)
    assert "Duquesne Family Office" in b
    assert "3.38B" in b
    assert "General Counsel" in b


def test_metadata_has_filter_fields():
    m = build_metadata(ROW)
    assert m["firm_type"] == "Unconfirmed"
    assert m["has_phone"] is True
    assert m["has_email"] is False
