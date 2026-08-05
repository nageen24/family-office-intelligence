"""Source interleave: name-only firms are spread through the pool, not stuck at
the back, so the climb stops being ADV/website-only."""
from pipeline.build_candidates import interleave_name_only
from pipeline.schema import CandidateFirm


def _firm(name, site=None):
    f = CandidateFirm(firm_name=name, discovery_source="t")
    f.website = site
    return f


def test_name_only_firms_appear_early_not_only_at_the_back():
    have = [_firm(f"S{i}", f"https://s{i}.com") for i in range(9)]
    none = [_firm(f"N{i}") for i in range(3)]
    out = interleave_name_only(have + none, every=4)
    names = [f.firm_name for f in out]
    # every 4th slot is a name-only firm
    assert names[3].startswith("N") and names[7].startswith("N")
    # a name-only firm lands within the first batch, not after all website firms
    assert any(n.startswith("N") for n in names[:6])
    assert len(out) == 12                       # nothing dropped


def test_order_within_each_group_is_preserved():
    have = [_firm(f"S{i}", f"https://s{i}.com") for i in range(6)]
    none = [_firm(f"N{i}") for i in range(2)]
    out = [f.firm_name for f in interleave_name_only(have + none, every=4)]
    assert [n for n in out if n.startswith("S")] == ["S0", "S1", "S2", "S3", "S4", "S5"]
    assert [n for n in out if n.startswith("N")] == ["N0", "N1"]


def test_leftovers_appended_when_one_group_exhausts():
    have = [_firm("S0", "https://s0.com")]
    none = [_firm(f"N{i}") for i in range(5)]
    out = [f.firm_name for f in interleave_name_only(have + none, every=4)]
    assert set(out) == {"S0", "N0", "N1", "N2", "N3", "N4"}
    assert len(out) == 6                         # no infinite loop, no loss


def test_all_website_or_all_name_only_is_safe():
    allsite = [_firm(f"S{i}", f"https://s{i}.com") for i in range(3)]
    assert len(interleave_name_only(allsite)) == 3
    allname = [_firm(f"N{i}") for i in range(3)]
    assert len(interleave_name_only(allname)) == 3


def test_name_only_ordered_registered_entities_before_news():
    from pipeline.build_candidates import interleave_name_only
    def nf(name, src):
        f = CandidateFirm(firm_name=name, discovery_source=src)
        f.website = None
        return f
    have = [_firm(f"S{i}", f"https://s{i}.com") for i in range(9)]
    none = [nf("NewsJunk", "Google News RSS"),
            nf("RealEdgar", "SEC EDGAR full-text search"),
            nf("Real990", "ProPublica Nonprofit Explorer (Form 990)")]
    out = [f.firm_name for f in interleave_name_only(have + none, every=4)]
    name_only_order = [n for n in out if n in ("NewsJunk", "RealEdgar", "Real990")]
    assert name_only_order == ["RealEdgar", "Real990", "NewsJunk"]  # news last
