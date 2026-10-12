import pytest
from adfl.evaluation import attribution_metrics, paired_intervention, plan_metrics, score_line
from adfl.world import CDW


def test_p1_ground_truth_scoring():
    assert attribution_metrics("H", "H", [])["attribution_correct"] is True
    assert attribution_metrics("H", "E", [])["attribution_correct"] is False
    assert attribution_metrics(None, "U", [])["attribution_correct"] is None
    h = [{"action":{"kind":"apply_change","target":"A"}}] * 3
    assert attribution_metrics("E","E",h)["invalid_retries"] == 2


def test_p2_does_not_equate_repetition_and_adoption():
    record = dict(condition="user",success=False,reception=True,belief_adoption=False,action_change=False)
    m = score_line("p2",[record])
    assert m["measurements"][0]["reception"] is True
    assert m["measurements"][0]["belief_adoption"] is False
    assert m["groups"]["user"]["successes"] == 0


@pytest.mark.parametrize("base,changed,delta,harm,recovery",[(True,False,-1,True,False),(False,True,1,False,True),(True,True,0,False,False)])
def test_p3_paired_net_value(base,changed,delta,harm,recovery):
    m = paired_intervention(dict(checkpoint_hash="x",success=base,cost=1),dict(checkpoint_hash="x",success=changed,cost=3))
    assert m == dict(paired_success_delta=delta,extra_cost=2,harm=harm,recovery=recovery)
    with pytest.raises(ValueError): paired_intervention(dict(checkpoint_hash="x"),dict(checkpoint_hash="y"))


def test_p4_unknown_oracle_is_missing():
    m = score_line("p4",[dict(condition="greedy",success=False,action_cost=4,regret=None)])
    assert "regret" in m["unmeasured"]


def test_p5_invalid_action_and_retention():
    w = CDW(); w.reset("plan:H")
    w.step({"kind":"apply_change","target":"A"})
    m = plan_metrics(w.s["history"], w.s["invalid_nodes"])
    assert m["invalid_action_rate"] == 1 and m["valid_node_retention"] is None
