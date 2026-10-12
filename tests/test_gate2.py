import copy
import json
from pathlib import Path
import pytest
from adfl.world import CDW
from adfl.world.pilot import PilotWorld
from adfl.pilot_design import P1_ARMS,P5_ARMS,session_for,channel_pair,ordered_runs
from adfl.gate2 import PilotEngine,config
from adfl.gate1 import fingerprint
from adfl.budget.ledger import Ledger
from adfl.budget.guard import BudgetStop


@pytest.mark.parametrize('family',['ambiguous','dependency','complementary'])
@pytest.mark.parametrize('truth',['H','E'])
def test_pilot_checkpoint_replay(family,truth):
    w=PilotWorld(); w.reset(family+':'+truth,0); cp=json.loads(json.dumps(w.snapshot())); h=w.checkpoint_hash()
    actions=[{'kind':'inspect','target':'B'},{'kind':'apply_change','target':'B'},{'kind':'diagnose','target':'B'},{'kind':'verify'}]
    first=[w.step(a) for a in actions]; score=w.score()
    w.restore(cp); assert w.checkpoint_hash()==h
    assert [w.step(a) for a in actions]==first and w.score()==score


def test_ambiguous_truth_not_visible_and_recovery_distinguishable():
    h=PilotWorld(); e=PilotWorld()
    assert h.reset('ambiguous:H')==e.reset('ambiguous:E')
    assert h.step({'kind':'diagnose','target':'A'})!=e.step({'kind':'diagnose','target':'A'})
    h.step({'kind':'apply_change','target':'A'}); assert not h.step({'kind':'verify'})['completed']
    h.step({'kind':'apply_change','target':'B'}); assert h.step({'kind':'verify'})['completed']
    e.step({'kind':'apply_change','target':'A'}); assert e.step({'kind':'verify'})['completed']


def test_plan_partial_invalidation_and_cost_distinction():
    w=PilotWorld(); w.reset('dependency:H'); cp=w.snapshot()
    assert w.s['world_state']['prepared'] and w.s['world_state']['calibrated']
    # Faithfully following the old pending plan now fails.
    for a in [{'kind':'apply_change','target':'A'},{'kind':'diagnose','target':'A'},{'kind':'verify'}]: w.step(a)
    assert not w.score()['success'] and w.score()['stale_node_executions']==2
    suffix=[{'kind':'inspect','target':'B'},{'kind':'apply_change','target':'B'},{'kind':'diagnose','target':'B'},{'kind':'verify'}]
    w.restore(cp)
    for a in suffix: w.step(a)
    selective=w.score(); assert selective['success'] and selective['valid_node_retention']==1
    w.restore(cp)
    for a in [{'kind':'prepare'},{'kind':'calibrate'}]+suffix: w.step(a)
    full=w.score(); assert full['success'] and full['valid_node_retention']==0
    assert full['tool_calls']-selective['tool_calls']==2
    assert selective['invalid_action_rate']==0


@pytest.mark.parametrize('line,arms',[('p1',P1_ARMS),('p5',P5_ARMS)])
def test_paired_fairness_and_intervention_delivery(line,arms):
    sessions=[session_for(line,a) for a in arms]
    assert len({s['checkpoint_hash'] for s in sessions})==1
    assert all(s['initial']==sessions[0]['initial'] for s in sessions)
    assert all(s['messages'][:2]==sessions[0]['messages'][:2] for s in sessions)
    assert len({json.dumps(s['messages']) for s in sessions})==len(arms)
    for s in sessions:
        context=json.dumps(s['messages'])
        for hidden in ('root_cause','execution_fault','rng_state','invalid_nodes','world_state'):
            assert hidden not in context
        if 'oracle' not in s['condition']: assert 'Privileged evaluator' not in context


def test_p2_exact_fact_and_native_tool_history_matched():
    fact='Verified: configuration B is required.'
    arms=channel_pair([{'role':'system','content':'same'}],fact)
    u,t=arms['user'],arms['tool']
    assert u[:-2]==t[:-2]
    assert u[-1]['content']==t[-2]['content']==fact
    assert u[-2]['content']==t[-1]['content']
    assert u[-2]['tool_call_id']==t[-2]['tool_call_id']==u[-3]['tool_calls'][0]['id']


def test_p3_natural_success_and_possible_harm_kept():
    w=PilotWorld(); w.reset('ambiguous:E'); cp=w.snapshot()
    for a in [{'kind':'apply_change','target':'A'},{'kind':'verify'}]: w.step(a)
    assert w.score()['success']
    w.restore(cp)
    for a in [{'kind':'apply_change','target':'B'},{'kind':'verify'}]: w.step(a)
    assert not w.score()['success']  # do not discard naturally successful baseline


def test_p4_preparation_complements_and_dual_effect():
    w=PilotWorld(); w.reset('complementary:H')
    assert 'inconclusive' in w.step({'kind':'diagnose','target':'A'})['feedback']
    w.step({'kind':'calibrate'})
    first=w.step({'kind':'diagnose','target':'A'}); second=w.step({'kind':'diagnose','target':'B'})
    assert 'bit:' in first['feedback'] and 'bit:' in second['feedback']
    w.step({'kind':'apply_change','target':'B'}); assert w.step({'kind':'verify'})['completed']
    w.reset('dependency:H'); before=w.s['staged']
    obs=w.step({'kind':'inspect','target':'B'})
    assert before=='A' and w.s['staged']=='B' and 'inspected' in obs['feedback']


def registered_pilot(tmp_path,c,cap=5000000):
    l=Ledger(tmp_path/'ledger.sqlite3',create=True); fp=fingerprint(c)
    for rid,line,arm in ordered_runs(): l.register(rid,fp,session_for(line,arm),spend_cap=1000000)
    l.authorize_pilot(c['batch_id'],[r[0] for r in ordered_runs()],fp,'synthetic only',cap=cap)
    return l


def test_pilot_real_transport_mock_and_interrupt_recovery(tmp_path):
    c=config(); l=registered_pilot(tmp_path,c); rid='g2-p1-no_intervention'; calls=[]
    acts=iter([{'kind':'diagnose','target':'A'},{'kind':'apply_change','target':'B'},{'kind':'verify'}])
    def transport(p,**kw):
        calls.append(copy.deepcopy(p))
        if len(calls)>1: assert p['messages'][-1]['role']=='tool'
        action=next(acts)
        return {'status':200,'body':{'model':c['model_id'],'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':None,
            'tool_calls':[{'id':'mock-'+str(len(calls)),'type':'function','function':{'name':'cdw_action','arguments':json.dumps({'action':action})}}]}}],
            'usage':{'prompt_tokens':300,'completion_tokens':50,'total_tokens':350}}}
    original=l.apply; interrupted=[]
    def apply(*a,**kw):
        if not interrupted: interrupted.append(True); raise KeyboardInterrupt()
        return original(*a,**kw)
    l.apply=apply
    with pytest.raises(KeyboardInterrupt): PilotEngine(l,c,transport).run(rid)
    assert len(calls)==1
    result=PilotEngine(Ledger(l.path),c,transport).run(rid)
    assert len(calls)==3 and result['runs'][0]['status']=='completed'
    assert result['unreconciled_requests']==3
    assert all(r['billed'] is None for r in result['requests'])


def test_pilot_batch_limit_cross_process(tmp_path):
    c=config(); l=registered_pilot(tmp_path,c,cap=1000); rid='g2-p1-no_intervention'; fp=fingerprint(c)
    req=l.reserve(rid,fp,1,1000,{})
    l.receive(req,{},None,None,allow_estimate=True)
    s=json.loads(l.snapshot(rid)['runs'][0]['session']); s['decisions']=1
    l.apply(req,s,{},terminal=True)
    with pytest.raises(BudgetStop,match='batch cap'): Ledger(l.path).reserve('g2-p5-belief_only',fp,1,1,{})
    assert Ledger(l.path).snapshot()['exposure_micro_cny']==1000


def test_original_gate1_world_still_unmodified():
    w=CDW(); assert w.reset('attribution:H')['remaining_actions']==12
    assert w.step({'kind':'diagnose'})['feedback']=='Required target B. Prior target A is incompatible.'


def test_gate2_cumulative_cap_includes_historical_liability(tmp_path):
    c=config(); l=registered_pilot(tmp_path,c); fp=fingerprint(c)
    rid='g2-p1-no_intervention'; req=l.reserve(rid,fp,1,1000,{})
    l.receive(req,{},None,None,allow_estimate=True)
    s=json.loads(l.snapshot(rid)['runs'][0]['session']); s['decisions']=1
    l.apply(req,s,{},terminal=True)
    # Synthetic historical unbilled liability near cumulative cap, not a new call.
    with l.transaction() as db:
        db.execute('UPDATE requests SET run=?,reserved=? WHERE id=?',('historical-gate1',39999999,req))
        db.execute('UPDATE account SET cap=100000000 WHERE id=1')
    with pytest.raises(BudgetStop,match='cumulative'): Ledger(l.path).reserve('g2-p5-belief_only',fp,1,2,{})
    assert Ledger(l.path).snapshot()['exposure_micro_cny']==39999999
