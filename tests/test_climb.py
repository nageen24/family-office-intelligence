"""S16/S17 — one idempotent climb increment.

climb_once processes the next batch of un-attempted candidates, merges results into
durable state, and rewrites the accumulating dataset. Re-running with the same
candidates does no work (idempotent) — the scheduler can fire repeatedly and only
ever make forward progress.
"""
from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.climb import climb_once

PAGE = ("About Cedar Family Office. We are a multi-family office serving several "
        "families. Jane Cedar, Managing Partner. Email jane.cedar@cedarfo.com.")


def _chat(system, user):
    if "principal_name" in system:
        return '{"principal_name": "Jane Cedar", "principal_title": "Managing Partner"}'
    return ('{"is_family_office": true, "function_quote": "We are a multi-family '
            'office serving several families", "type": "multi", "type_quote": '
            '"multi-family office serving several families", '
            '"sec_family_office_exemption": false}')


def _cands():
    # real ADV candidates carry a firm-level background note (Item 5.D) so they
    # clear the thinness floor even when a contact cell is later withheld
    bg = lambda: Cell(value="Reports HNW individual clients on its own Form ADV.",
                      source="SEC Form ADV", epistemic=Epistemic.FACT)
    a = CandidateFirm(firm_name="Cedar Family Office", discovery_source="SEC Form ADV")
    a.website = "https://cedarfo.com"; a.background = bg()
    b = CandidateFirm(firm_name="Birch Family Office", discovery_source="SEC Form ADV")
    b.website = "https://birchfo.com"; b.background = bg()
    return [a, b]


def test_climb_once_accumulates_and_writes_dataset(tmp_path):
    state_path = str(tmp_path / "state.json")
    summary = climb_once(batch_size=10, candidates=_cands(), chat=_chat,
                         fetch=lambda u: PAGE, state_path=state_path,
                         out_dir=str(tmp_path), min_interval=0, workers=2)
    assert summary["attempted_total"] == 2
    assert summary["qualified_total"] == 2
    assert (tmp_path / "dataset_stage2.csv").exists()


def test_climb_once_is_idempotent_on_rerun(tmp_path):
    state_path = str(tmp_path / "state.json")
    kw = dict(candidates=_cands(), chat=_chat, fetch=lambda u: PAGE,
              state_path=state_path, out_dir=str(tmp_path), min_interval=0, workers=2)
    climb_once(batch_size=10, **kw)
    second = climb_once(batch_size=10, **kw)
    assert second["processed_this_run"] == 0        # nothing left to do
    assert second["attempted_total"] == 2           # state unchanged
