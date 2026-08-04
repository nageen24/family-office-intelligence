"""S16 — durable, idempotent climb state (restart-safe, replayable via git).

The scheduled climb persists which firms it has already attempted and the records
it has accumulated, so: reruns never redo work (idempotent), a crash loses at most
the in-flight batch (restart-safe), and the git history of the state file is the
replay log.
"""
from pipeline.schema import CandidateFirm
from pipeline.state import firm_key, unattempted, merge_pool, save_state, load_state


def _f(name, **kw):
    f = CandidateFirm(firm_name=name, discovery_source="SEC Form ADV")
    for k, v in kw.items():
        setattr(f, k, v)
    return f


def test_firm_key_is_stable_and_normalized():
    assert firm_key(_f("Cherry Creek Family Offices")) == firm_key(_f("CHERRY  CREEK   family offices"))


def test_unattempted_skips_firms_already_in_state():
    state = {firm_key(_f("Colony Family Offices")): _f("Colony Family Offices")}
    cands = [_f("Colony Family Offices"), _f("Riverglades Family Offices")]
    todo = unattempted(cands, state)
    assert [c.firm_name for c in todo] == ["Riverglades Family Offices"]


def test_merge_is_idempotent():
    state = {}
    merge_pool(state, [_f("Colony Family Offices", record_status="Qualified")])
    merge_pool(state, [_f("Colony Family Offices", record_status="Qualified")])
    assert len(state) == 1


def test_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "climb.json")
    state = {}
    merge_pool(state, [_f("Colony Family Offices", record_status="Qualified"),
                       _f("Riverglades Family Offices", record_status="Rejected")])
    save_state(path, state)
    loaded = load_state(path)
    assert len(loaded) == 2
    assert firm_key(_f("Colony Family Offices")) in loaded


def test_load_missing_file_is_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {}
