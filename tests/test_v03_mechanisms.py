import copy
import json
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path
import pytest
from adfl.v03.world import World, shortest_success, digest
from adfl.v03.design import context, role_contexts, scripted, TOOL
from adfl.v03.pomdp import prior, branches, policy_value, solve, select, entropy, transition


@pytest.mark.parametrize('seed',[0,1])
def test_p1_matched_failure_requires_different_repair(seed):
    h,e = World('P1','H',seed),World('P1','E',seed)
    assert context(h)==context(e)
    assert h.step({'kind':'receipt'}) != e.step({'kind':'receipt'})
    assert h.step({'kind':'compatibility'}) != e.step({'kind':'compatibility'})
    for w,target in [(h,h.s['alternative']),(e,e.s['prior'])]:
        w.step({'kind':'apply','target':target}); w.step({'kind':'verify'})
        assert w.score()['task_success']


@pytest.mark.parametrize('seed',[0,1])
def test_p1_observation_error_is_not_execution_error(seed):
    w=World('P1','O',seed)
    assert 'delivered' in w.step({'kind':'receipt'})['observation']
    assert 'compatible' in w.step({'kind':'compatibility'})['observation']
    assert not w.step({'kind':'verify'})['terminal']
    assert 'stale' in w.step({'kind':'audit_monitor'})['observation']
    w.step({'kind':'verify'})
    assert w.score()['task_success'] and not any(h['action']['kind']=='apply' for h in w.s['history'])


def test_p1_insufficient_evidence_two_worlds_same_view():
    a,b=World('P1','U',0),World('P1','U',2)
    assert context(a)==context(b)
    assert a.s['hidden']['target']!=b.s['hidden']['target']
    # A single unconditioned modification cannot be right in both worlds.
    a.step({'kind':'apply','target':'A'}); b.step({'kind':'apply','target':'A'})
    a.step({'kind':'verify'}); b.step({'kind':'verify'})
    assert a.score()['task_success'] != b.score()['task_success']


@pytest.mark.parametrize('seed',[0,1])
@pytest.mark.parametrize('unreliable',[False,True])
def test_p2_native_history_content_and_budget_matched(seed,unreliable):
    design=role_contexts(World('P2','H',seed),unreliable)
    gs=design['histories']
    assert gs['C1'][-1]['content']==gs['C2'][-2]['content']
    assert len(json.dumps(gs['C1']).encode())==len(json.dumps(gs['C2']).encode())
    assert all(m['role']!='tool' or m['tool_call_id']==gs[g][-3]['tool_calls'][0]['id']
               for g in gs for m in gs[g] if m['role']=='tool')
    assert all(gs[g][1]==gs['C0'][1] for g in gs)
    assert design['checkpoint']['state']['remaining']==11
    assert design['checkpoint']['state']['history']==design['raw_tool_checkpoint']['state']['history']
    raw=design['raw_tool_checkpoint']['state']['last']
    if unreliable and seed % 5 == 0:
        assert ('incompatible' in raw) != ('incompatible' in design['fact'])
    else:
        assert raw in design['fact']


def test_p3_proves_recoverability_and_intervention_harm():
    for family,feasible in [('recoverable',True),('fragile_success',True),('irrecoverable',False)]:
        assert shortest_success(World('P3',family))['feasible']==feasible
    good=scripted(World('P3','fragile_success'),[{'kind':'wait'},{'kind':'verify'}])
    bad=scripted(World('P3','fragile_success'),[{'kind':'rollback'},{'kind':'advance'},{'kind':'advance'},{'kind':'verify'}])
    assert good['score']['task_success'] and not bad['score']['task_success']
    repair=scripted(World('P3','recoverable'),[{'kind':'advance'},{'kind':'advance'},{'kind':'verify'}])
    assert repair['score']['task_success']


@pytest.mark.parametrize('family',['A','B','C'])
def test_p5_dag_truth_and_multiple_valid_orders(family):
    w=World('P5',family)
    assert len(w.s['deps']['merge'])==2
    assert w.valid('credentials')
    if family=='A':
        assert w.valid('snapshot') and w.valid('right') and not w.valid('left')
    elif family=='B':
        assert not w.valid('snapshot') and not w.valid('left') and not w.valid('right')
    else:
        assert all(w.valid(n) for n in ('snapshot','credentials','left','right'))
    oracle=shortest_success(w,8)
    assert oracle['feasible']
    result=scripted(w,oracle['actions'])
    assert result['score']['task_success'] and result['score']['valid_work_retention']==1
    assert result['score']['unnecessary_reexecution']==0
    for ordering in [('snapshot','credentials','left','right'),('credentials','snapshot','right','left')]:
        w2=World('P5',family)
        result=scripted(w2,[{'kind':'execute_node','node':n} for n in ordering+('merge','publish')]+[{'kind':'verify'}])
        assert result['score']['task_success']


def test_p5_false_alarm_and_generation_invalidation():
    w=World('P5','C',0)
    assert 'revision 1' in w.step({'kind':'audit'})['observation']
    w.step({'kind':'execute_node','node':'snapshot'})
    assert w.valid('snapshot') and not w.valid('left') and not w.valid('right')
    assert w.score()['unnecessary_reexecution']==1
    assert w.step({'kind':'execute_node','node':'merge'})['observation'].endswith('invalid prerequisite')
    assert w.score()['obsolete_action_attempts']==1 and w.score()['obsolete_action_execution']==0
    changed=World('P5','C',1)
    assert not changed.valid('snapshot') and 'revision 2' in changed.step({'kind':'audit'})['observation']


@pytest.mark.parametrize('line,family',[('P1','H'),('P1','E'),('P1','O'),('P1','U'),('P3','fragile_success'),('P5','B')])
def test_checkpoint_disk_replay_and_public_truth_isolation(tmp_path,line,family):
    w=World(line,family); cp=w.snapshot(); path=tmp_path/'checkpoint.json'
    path.write_text(json.dumps(cp),encoding='utf-8')
    r=World.restore(json.loads(path.read_text(encoding='utf-8')))
    assert r.snapshot()==cp
    for action in w.actions():
        a,b=World.restore(cp),World.restore(cp)
        assert a.step(action)==b.step(action) and a.score()==b.score()
    cp['state']['hidden']['private_sentinel']='NEVER_TO_AGENT_7f4a'
    public=json.dumps(context(World.restore(cp)))
    assert 'NEVER_TO_AGENT_7f4a' not in public
    assert all(k not in r.observe() for k in ('hidden','family','seed','required','task_id'))


def test_checkpoint_cross_process(tmp_path):
    cp=World('P5','B').snapshot(); path=tmp_path/'cp.json'; path.write_text(json.dumps(cp),encoding='utf-8')
    code='import json,sys; from adfl.v03.world import World,digest; w=World.restore(json.load(open(sys.argv[1]))); print(digest(w.snapshot()))'
    import os
    env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','TEMP','TMP') if k in os.environ}
    env['PYTHONPATH']=str(Path('src').resolve())
    p=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,check=True,env=env)
    assert p.stdout.strip()==digest(cp)


def test_action_schema_rejects_ignored_or_extra_arguments():
    w=World('P5','B'); cp=w.snapshot()
    for bad in ({'kind':'execute_node','node':'left','target':'B'},{'kind':'prepare','target':'B'},{'kind':'audit','target':'A'}):
        with pytest.raises(ValueError): w.step(bad)
        assert w.snapshot()==cp


def test_p1_diagnostic_is_real_and_costed_without_mutating_shared_checkpoint():
    from adfl.v03.design import intervention
    w=World('P1','E'); cp=w.snapshot()
    branch,messages=intervention(w,'diagnostic_evidence')
    assert w.snapshot()==cp and branch.s['remaining']==11
    assert messages[-1]['role']=='tool' and 'absent' in messages[-1]['content']
    assert 'PRIVILEGED' in json.dumps(context(w,'oracle_failure_class'))


def test_read_only_ledger_audit_preserves_unknown_liabilities(tmp_path):
    import sqlite3
    from adfl.v03.stage_a import ledger_audit
    path=tmp_path/'ledger.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE requests(id TEXT,run TEXT,step INTEGER,reserved INTEGER,calculated INTEGER,billed INTEGER,status TEXT)')
        db.executemany('INSERT INTO requests VALUES(?,?,?,?,?,?,?)',[
            ('old:0','old',0,500000,None,None,'unknown'),('old:1','old',1,800000,300000,300000,'settled')])
    before=path.read_bytes(); audit=ledger_audit(path)
    assert audit['exposure_micro_cny']==800000 and audit['unsettled']==1
    assert path.read_bytes()==before


def test_p3_three_prespecified_conditions_are_real_distinct_interventions():
    from adfl.v03.design import intervention,P3_CONDITIONS
    for family,conditions in P3_CONDITIONS.items():
        w=World('P3',family); cp=w.snapshot(); outputs=[]
        for condition in conditions:
            branch,msgs=intervention(w,condition)
            outputs.append(json.dumps({'state':branch.snapshot(),'messages':msgs},sort_keys=True))
            assert w.snapshot()==cp
        assert len(set(outputs))==3


@pytest.mark.parametrize('family',['A','B','C','D'])
def test_p4_exact_probability_and_baseline_bounds(family):
    b=prior(family)
    assert sum(p for _,p in b)==1
    from adfl.v03.pomdp import ACTIONS
    for action in ACTIONS[family]:
        r,terminal,bs=branches(family,b,action)
        assert sum(p for p,_,_ in bs)==1
        assert all(sum(q for _,q in posterior)==1 for _,posterior,_ in bs)
    optimum=policy_value(family,'exact')
    assert optimum == {'A':F(17,20),'B':F(17,20),'C':F(9,10),'D':F(9,10)}[family]
    assert optimum==solve(family,b,4)[0]
    for baseline in ('immediate','information_gain','lookahead2'):
        assert policy_value(family,baseline)<=optimum
    # Honest negative result: stronger two-step baseline already solves these fixtures.
    assert policy_value(family,'lookahead2')==optimum


def test_p4_preparation_and_complementarity_have_no_immediate_ig():
    for family,action in [('A','calibrate'),('B','probe1')]:
        b=prior(family); _,_,bs=branches(family,b,action)
        assert abs(entropy(family,b)-sum(float(p)*entropy(family,c) for p,c,_ in bs))<1e-12
        assert policy_value(family,'exact')>policy_value(family,'information_gain')
    assert select('C',prior('C'),4,'exact')=='dual'
    assert select('D',prior('D'),4,'exact')=='wait'
    s=(0,0,0,0,0,2)
    assert transition('D',s,'guess0')[0][3]==-F(1,20)


@pytest.mark.parametrize('family',['A','B','C','D'])
def test_p4_realized_recovery_and_policy_uses_only_public_belief(family):
    from adfl.v03.pomdp import BeliefSession
    values=[]
    for seed in range(len(prior(family))):
        s=BeliefSession(family,seed)
        while not s.terminal and s.remaining:
            clone=BeliefSession.restore(json.loads(json.dumps(s.snapshot())))
            a=select(family,s.belief,s.remaining,'exact')
            assert clone.step(a)==s.step(a)
            assert clone.snapshot()==s.snapshot()
        values.append(s.utility)
    assert sum(values)/len(values)==policy_value(family,'exact')


def test_stage_a_has_no_network_and_never_evaluates_holdout(tmp_path,monkeypatch):
    import sqlite3
    import urllib.request
    import adfl.v03.stage_a as stage
    def no_network(*args,**kwargs):
        raise AssertionError('Stage A fixture generation must not use network')
    monkeypatch.setattr(urllib.request,'urlopen',no_network)
    planner=stage.shortest_success
    def dev_only(world,*args,**kwargs):
        assert world.s['seed']<1000, 'holdout was evaluated'
        return planner(world,*args,**kwargs)
    monkeypatch.setattr(stage,'shortest_success',dev_only)
    (tmp_path/'.state').mkdir(); (tmp_path/'research').mkdir()
    with sqlite3.connect(tmp_path/'.state/gate1.sqlite3') as db:
        db.execute('CREATE TABLE requests(id TEXT,run TEXT,step INTEGER,reserved INTEGER,calculated INTEGER,billed INTEGER,status TEXT)')
        db.execute("INSERT INTO requests VALUES('old:0','old',0,500000,NULL,NULL,'unknown')")
    summary=stage.generate(tmp_path)
    assert summary['manifest_rows']==144 and summary['ledger_exposure_cny']==0.5
