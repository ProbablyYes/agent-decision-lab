import json
import pytest
from adfl.world import CDW
from adfl.agents import APIAgent, MockAgent, FrozenConfig
from adfl.budget import BudgetGuard, Pricing, BudgetStop
from adfl.runner import fixture, run_episode
from adfl.evaluation import score_line
from adfl.interventions import feedback, fork


@pytest.mark.parametrize("line", ["p1", "p2", "p3", "p4", "p5"])
@pytest.mark.parametrize("variant", ["H", "E", "U"])
def test_fixtures(tmp_path, line, variant):
    task, actions = fixture(line, variant)
    result = run_episode(tmp_path / line, task, MockAgent(actions), line)
    assert result["success"] and result["actual_api_cost_cny"] == 0
    assert result["tool_calls"] == len(actions)
    assert score_line(line, [result])["groups"]["scripted_calibration"]["successes"] == 1
    public = (tmp_path / line / "trajectory.jsonl").read_text()
    for key in ("root_cause", "execution_fault", "observation_reliability", "world_state", "rng_state", "plan_DAG"):
        assert key not in public
    assert "belief_adoption" in score_line("p2", [result])["unmeasured"]


@pytest.mark.parametrize("family", ["attribution", "plan", "complement"])
def test_replay(family):
    w = CDW(); w.reset(family + ":E", 17)
    cp = json.loads(json.dumps(w.snapshot()))
    digest = w.checkpoint_hash()
    actions = [{"kind": "prepare"}, {"kind": "apply_change", "target": "A"}, {"kind": "verify"}]
    first = [w.step(a) for a in actions]; final = w.checkpoint_hash()
    w.restore(cp)
    assert w.checkpoint_hash() == digest
    assert [w.step(a) for a in actions] == first
    assert w.checkpoint_hash() == final


def test_dag_and_real_effects():
    w = CDW(); w.reset("plan:H")
    assert w.s["plan_DAG"]["apply"] == ["prepare"]
    assert w.s["invalid_nodes"] == ["apply", "verify"]
    w.step({"kind": "apply_change", "target": "B"}); assert not w.score()["success"]
    w.step({"kind": "combo", "actions": [{"kind": "prepare"}, {"kind": "apply_change", "target": "B"}, {"kind": "verify"}]})
    assert w.score()["success"] and w.score()["tool_calls"] == 4
    w.step({"kind": "undo"}); assert not w.score()["success"]
    assert w.s["world_state"]["prepared"]


def test_complement_and_ambiguity():
    w = CDW(); w.reset("complement:H")
    assert "inconclusive" in w.step({"kind": "diagnose"})["feedback"]
    w.step({"kind": "calibrate"})
    assert "target B" in w.step({"kind": "diagnose"})["feedback"]
    w.reset("attribution:U")
    assert "insufficient" in w.step({"kind": "diagnose"})["feedback"]


@pytest.mark.parametrize("gate,threshold", [(1,10), (2,40), (4,90), (4,100)])
def test_budget_thresholds(gate, threshold):
    g = BudgetGuard(gate, True, 100, threshold)
    assert threshold in g.state()["thresholds_reached"]
    with pytest.raises(BudgetStop): g.reserve(.01)


def test_reservation_unknown_and_retry():
    g = BudgetGuard(1, True)
    g.reserve(1)
    with pytest.raises(BudgetStop): g.reserve(1)
    with pytest.raises(BudgetStop): g.settle(None, None)
    assert g.spent == 1
    with pytest.raises(BudgetStop): g.reserve(1)
    with pytest.raises(BudgetStop): BudgetGuard().reserve(0)


def test_cost_bound():
    p = Pricing(2, 8, "CNY", 1, "synthetic-test-only", "test", "test")
    assert p.estimate(1000, 500) == .006
    g = BudgetGuard(1, True, spent=9.999)
    with pytest.raises(BudgetStop): g.reserve(p.estimate(1000, 500))


@pytest.mark.parametrize("mode", ["timeout", "bad_json", "missing_usage", "billed_error"])
def test_api_failures_retained(tmp_path, mode):
    calls = []
    def transport(request):
        calls.append(request)
        if mode == "timeout": raise TimeoutError("synthetic timeout")
        if mode == "billed_error": return {"text": "", "usage": {"input_tokens": 10, "output_tokens": 0, "cached_tokens": 0}, "billed_cny": .001, "error": "synthetic provider failure"}
        return {"text": "{broken", "usage": None if mode == "missing_usage" else {"input_tokens": 10, "output_tokens": 1, "cached_tokens": 0}, "billed_cny": .001}
    a = APIAgent(FrozenConfig(model_id="fake"), transport)
    r = run_episode(tmp_path / mode, "attribution:H", a, guard=BudgetGuard(1, True), pricing=Pricing(2,8,"CNY",1,"test","test","test"))
    assert r["error"] and not r["excluded"] and len(calls) == 1
    assert "episode_failed" in (tmp_path / mode / "events.jsonl").read_text()
    assert (tmp_path / mode / "budget.json").exists()


def test_no_api_without_gate(tmp_path):
    calls = []
    a = APIAgent(FrozenConfig(model_id="fake"), lambda r: calls.append(r))
    r = run_episode(tmp_path / "blocked", "attribution:H", a, guard=BudgetGuard(), pricing=Pricing(2,8,"CNY",1,"test","test","test"))
    assert not calls and r["error"]


def test_feedback_and_fork():
    base = [{"role": "system", "content": "same"}]
    u, t = feedback(base,"user","Required target B"), feedback(base,"tool","Required target B")
    assert u[-1]["content"] == t[-1]["content"] and len(base) == 1
    w = CDW(); w.reset("plan:H"); cp = w.snapshot(); h = w.checkpoint_hash()
    w.step({"kind":"prepare"}); assert fork(w,cp,base) == base
    assert w.checkpoint_hash() == h


def test_negative_outcome_and_missing_arms(tmp_path):
    r = run_episode(tmp_path / "failure", "attribution:H", MockAgent([{"kind":"apply_change","target":"A"}]))
    assert not r["success"] and r["error"] and not r["excluded"]
    assert score_line("p5", [r])["groups"]["scripted_calibration"]["successes"] == 0


def test_api_interface_complete_loop_without_network(tmp_path):
    decisions = iter([{"kind":"diagnose"},{"kind":"apply_change","target":"B"},{"kind":"verify"}])
    calls = []
    def transport(req):
        calls.append(req)
        assert "root_cause" not in json.dumps(req)
        return {"text":json.dumps({"action":next(decisions)}),
                "usage":{"input_tokens":100,"output_tokens":20,"cached_tokens":0},"billed_cny":.001}
    a = APIAgent(FrozenConfig(model_id="fake"),transport)
    r = run_episode(tmp_path / "loop","attribution:H",a,guard=BudgetGuard(1,True),pricing=Pricing(2,8,"CNY",1,"test","test","test"))
    assert r["success"] and len(calls) == 3 and r["actual_api_cost_cny"] == .003
    session = json.loads((tmp_path / "loop" / "hidden" / "session.json").read_text())
    w = CDW(); w.restore(session["environment"])
    assert w.score()["success"] and len(session["messages"]) == 8
    assert session["agent_fingerprint"] == a.fingerprint()


def test_config_rejects_tuning(tmp_path):
    from adfl.config import load_config
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(dict(protocol="V0.2",gate=0,tune_on_test=True,automatic_retries=0,concurrency=1)))
    with pytest.raises(ValueError): load_config(path)
