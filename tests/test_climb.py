"""S16/S17 — one idempotent climb increment.

climb_once processes the next batch of un-attempted candidates, merges results into
durable state, and rewrites the accumulating dataset. Re-running with the same
candidates does no work (idempotent) — the scheduler can fire repeatedly and only
ever make forward progress.
"""
from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.climb import climb_once

PAGE = ("About Cedar Family Office. We are a multi-family office serving several "
        "families. Jane Cedar, Managing Partner. Email jane.cedar@cedarfo.com. "
        "Jane on LinkedIn: https://www.linkedin.com/in/jane-cedar")


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
    summary = climb_once(batch_size=10, add_news=False, candidates=_cands(), chat=_chat,
                         fetch=lambda u: PAGE, state_path=state_path,
                         out_dir=str(tmp_path), min_interval=0, workers=2)
    assert summary["attempted_total"] == 2
    assert summary["qualified_total"] == 2
    assert (tmp_path / "dataset.csv").exists()


def test_recheck_detects_a_demotion_for_replenishment():
    # a qualified, stale record whose live site now contradicts its stored proof
    from pipeline.climb import _recheck_stale
    from pipeline.state import firm_key
    f = CandidateFirm(firm_name="Old Family Office", discovery_source="SEC Form ADV")
    f.website = "https://old.com"
    f.proof_function_source = f.website
    f.proof_function_quote = "Old is a single family office"
    f.record_status = "Qualified"
    f.last_verified = "2026-06-01"
    state = {firm_key(f): f}
    rechecked, demoted, catches = _recheck_stale(
        state, lambda u: "We are now a commercial bank.", "2026-08-04", limit=5)
    assert rechecked == 1 and demoted == 1                 # demotion counted -> climb replenishes
    assert f.proof_function_quote is None                  # contradicted proof withheld
    assert f.record_status != "Qualified"
    # the catch surfaces in the run summary with its evidence-based reason
    assert catches[0]["firm"] == "Old Family Office"
    assert catches[0]["trust"] == "contradicted"
    assert "no longer present" in catches[0]["reason"]


def test_recheck_fires_within_operating_window(monkeypatch):
    # a 5-day mandate cannot wait 14 days: a record proven 2 days ago is due
    from pipeline.climb import _recheck_stale
    from pipeline.state import firm_key
    f = CandidateFirm(firm_name="Fresh FO", discovery_source="SEC Form ADV")
    f.website = "https://fresh.com"
    f.proof_function_quote = "Fresh FO is a family office"
    f.last_verified = "2026-08-03"
    state = {firm_key(f): f}
    page = "Fresh FO is a family office"
    rechecked, _, catches = _recheck_stale(state, lambda u: page,
                                           "2026-08-05", limit=5)
    assert rechecked == 1 and not catches                  # unchanged -> fresh
    assert f.trust == "fresh" and f.last_verified == "2026-08-05"


def test_climb_once_is_idempotent_on_rerun(tmp_path):
    state_path = str(tmp_path / "state.json")
    kw = dict(candidates=_cands(), chat=_chat, fetch=lambda u: PAGE,
              state_path=state_path, out_dir=str(tmp_path), min_interval=0, workers=2)
    climb_once(batch_size=10, add_news=False, **kw)
    second = climb_once(batch_size=10, add_news=False, **kw)
    assert second["processed_this_run"] == 0        # nothing left to do
    assert second["attempted_total"] == 2           # state unchanged


def test_run_settings_scale_with_provider_count():
    from pipeline.climb import _run_settings
    # more providers -> bigger batch, tighter spacing (per-provider TPD/TPM add up)
    b2, i2, w2 = _run_settings(2, use_browser=False)
    b5, i5, w5 = _run_settings(5, use_browser=False)
    assert b2 == 36 and b5 == 90
    assert i2 == 10.0 and i5 == 4.0          # interval > 20/n, clamped [4,10]
    assert w2 == 6
    # browser layer is memory-heavy -> fewer workers
    assert _run_settings(5, use_browser=True)[2] == 3
    # floors/ceilings hold at the extremes
    assert _run_settings(1, use_browser=False)[0] == 35      # batch floor
    assert _run_settings(99, use_browser=False)[0] == 120    # batch ceiling
    assert _run_settings(0, use_browser=False)[1] == 10.0    # n coerced to >=1


def test_retighten_restores_quarantined_quote_that_now_passes():
    # a real MFO whose bare-predicate quote was quarantined under a too-strict gate
    from pipeline.climb import _retighten_function_proofs
    from pipeline.state import firm_key
    f = CandidateFirm(firm_name="Tillman Hartley", discovery_source="SEC Form ADV")
    f.website = "https://th.com"
    f.quarantined_function_quote = "An Independent Multi-Family Office and Wealth Management Firm"
    f.proof_function_quote = None
    f.fail_reason = "not-fo-identity-statement"
    changed = _retighten_function_proofs({firm_key(f): f})
    assert changed == 1
    assert f.proof_function_quote == "An Independent Multi-Family Office and Wealth Management Firm"
    assert f.quarantined_function_quote is None


def test_retighten_withholds_live_quote_that_fails():
    from pipeline.climb import _retighten_function_proofs
    from pipeline.state import firm_key
    f = CandidateFirm(firm_name="Serve Co", discovery_source="SEC Form ADV")
    f.website = "https://s.com"
    f.proof_function_quote = "We provide portfolio management for individuals and families."
    changed = _retighten_function_proofs({firm_key(f): f})
    assert changed == 1
    assert f.proof_function_quote is None
    assert f.quarantined_function_quote == "We provide portfolio management for individuals and families."
