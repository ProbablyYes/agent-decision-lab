import copy
import io
import json
import os
import subprocess
import sys
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from adfl.agents.tools import TOOLS, decode_tool
from adfl.agents.transport import OFoxTransport, redact, NoRedirect
from adfl.budget.guard import BudgetStop
from adfl.budget.ledger import Ledger
from adfl.budget.pricing import RateCard, usage_from
from adfl.gate1 import Gate1Engine, fingerprint, initial_session, readiness, export, first_run_report


@pytest.fixture
def config():
    c=json.loads(Path('configs/gate1.json').read_text(encoding='utf-8'))
    c['estimate_based_first_run_authorized']=False
    for k in ('model_confirmed','model_access_confirmed','account_currency_confirmed','account_rates_confirmed','fx_confirmed','usage_cache_semantics_confirmed'):
        c[k]=True
    c['pricing']['cache_write_semantics']='exclusive_prompt_subset'
    return c


def response(action,model='qwen/qwen-flash',**overrides):
    b={'model':model,'id':'fake-response','choices':[{'finish_reason':'tool_calls','message':{
        'role':'assistant','content':None,'tool_calls':[{'id':'call-1','type':'function','function':{
        'name':'cdw_action','arguments':json.dumps({'action':action})}}]}}],
        'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,
                 'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}}
    b.update(overrides)
    return {'status':200,'body':b,'raw':json.dumps(b),'request_id':'synthetic'}


def registered(tmp_path,config,run_id='g1-01',spend_cap=1000000):
    l=Ledger(tmp_path/'ledger.db',create=True)
    l.register(run_id,fingerprint(config),initial_session('attribution:H','p1'),spend_cap=spend_cap)
    l.approve(run_id,fingerprint(config),'synthetic test approval; not real authorization',ready=True)
    return l


class MockHTTP(io.BytesIO):
    status=200
    headers={'x-request-id':'test-http'}


def test_transport_mock_http_native_and_no_credential_at_init():
    loaded=[]; calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append(request)
            assert request.full_url=='https://api.ofox.ai/v1/chat/completions'
            assert request.method=='POST' and timeout==45
            assert request.get_header('Authorization')=='Bearer synthetic-credential'
            return MockHTTP(json.dumps(response({'kind':'verify'})['body']).encode())
    transport=OFoxTransport(key_loader=lambda: loaded.append(1) or 'synthetic-credential',opener=Opener())
    assert loaded==[]
    with pytest.raises(PermissionError): transport({})
    assert loaded==[] and calls==[]
    result=transport({'tools':TOOLS},send_authorized=True)
    assert result['status']==200 and loaded==[1] and len(calls)==1
    assert 'synthetic-credential' not in json.dumps(result)


@pytest.mark.parametrize('mode',['timeout','429','bad-json','redirect'])
def test_transport_failure_no_retry(mode):
    calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append(1)
            if mode=='timeout': raise TimeoutError('synthetic-credential should not leak')
            if mode in {'429','redirect'}:
                code=429 if mode=='429' else 302
                raise urllib.error.HTTPError(request.full_url,code,'bad',{},io.BytesIO(b'{"error":"synthetic-credential"}'))
            return MockHTTP(b'not-json')
    r=OFoxTransport(key_loader=lambda:'synthetic-credential',opener=Opener())({},send_authorized=True)
    assert len(calls)==1 and 'synthetic-credential' not in json.dumps(r)
    if mode=='timeout': assert r['transport_error']=='TimeoutError'
    if mode=='bad-json': assert r['body'] is None
    assert NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.test') is None


def test_price_currency_cache_and_unknown(config):
    rates=RateCard(config['pricing'])
    assert rates.reserve(8192,512)>0
    u=usage_from(response({'kind':'wait'})['body'])
    assert rates.calculated(u)>0
    body=response({'kind':'wait'})['body']; body['usage'].pop('prompt_tokens_details')
    missing=usage_from(body)
    assert missing['cached_tokens'] is None and rates.calculated(missing) is None
    bad=copy.deepcopy(config['pricing']); bad['cache_write']=None
    with pytest.raises(BudgetStop): RateCard(bad).reserve(8192,512)
    with pytest.raises(BudgetStop): usage_from({'usage':{'prompt_tokens':-1,'completion_tokens':1}})


def test_unconfirmed_configuration_blocks_send(tmp_path):
    c=json.loads(Path('configs/gate1.json').read_text(encoding='utf-8'))
    c['estimate_based_first_run_authorized']=False
    l=Ledger(tmp_path/'ledger.db',create=True)
    calls=[]
    with pytest.raises(BudgetStop): Gate1Engine(l,c,lambda *a,**kw:calls.append(1)).run('g1-01')
    assert not calls and not readiness(c)['ready_for_approval']


def test_full_native_loop_and_bill_review(tmp_path,config):
    l=registered(tmp_path,config)
    actions=iter([{'kind':'diagnose'},{'kind':'apply_change','target':'B'},{'kind':'verify'}])
    calls=[]
    def transport(payload,**kwargs):
        calls.append(copy.deepcopy(payload))
        assert kwargs['send_authorized'] is True
        assert 'root_cause' not in json.dumps(payload)
        return response(next(actions))
    s=Gate1Engine(l,config,transport).run('g1-01')
    assert len(calls)==3 and s['runs'][0]['status']=='completed'
    assert calls[1]['messages'][-1]['role']=='tool'
    assert calls[1]['messages'][-1]['tool_call_id']=='call-1'
    assert calls[1]['messages'][-2]['tool_calls'][0]['id']=='call-1'
    assert s['exposure_micro_cny']>s['actual_verified_micro_cny']==0
    with pytest.raises(BudgetStop): l.review('g1-01','review before billing')
    for r in s['requests']:
        l.reconcile(r['id'],r['calculated'],json.loads(r['usage']),'synthetic itemized bill')
    l.review('g1-01','synthetic review')
    export(l,config,'g1-01',tmp_path/'output')
    m=json.loads((tmp_path/'output/metrics.json').read_text())
    assert m['success'] and m['actual_api_cost_cny']>0
    assert not Gate1Engine(l,config,transport).run('g1-01')['unreconciled_requests']
    assert len(calls)==3  # Never repeat a terminal trajectory.


def test_restart_reservation_survives_process_exit(tmp_path,config):
    l=registered(tmp_path,config)
    code='from adfl.budget.ledger import Ledger; import sys,os; l=Ledger(sys.argv[1]); l.reserve("g1-01",sys.argv[2],1,1000,{"model":"fake"}); os._exit(0)'
    env={**os.environ,'PYTHONPATH':str(Path('src').resolve())}
    subprocess.run([sys.executable,'-c',code,str(l.path),fingerprint(config)],env=env,check=True)
    reopened=Ledger(l.path)
    assert reopened.snapshot()['exposure_micro_cny']==1000
    calls=[]
    with pytest.raises(BudgetStop): Gate1Engine(reopened,config,lambda *a,**k:calls.append(1)).run('g1-01')
    assert not calls
    with pytest.raises(FileExistsError): Ledger(l.path,create=True)


def test_received_response_recovery_does_not_repeat_http(tmp_path,config):
    l=registered(tmp_path,config)
    req=l.reserve('g1-01',fingerprint(config),1,1000,{'model':'fake'})
    r=response({'kind':'combo','actions':[{'kind':'apply_change','target':'B'},{'kind':'verify'}]})
    u=usage_from(r['body'])
    l.receive(req,r,u,RateCard(config['pricing']).calculated(u))
    calls=[]
    s=Gate1Engine(Ledger(l.path),config,lambda *a,**k:calls.append(1)).run('g1-01')
    assert not calls and s['runs'][0]['status']=='completed'
    assert json.loads(s['runs'][0]['session'])['decisions']==1


def test_transaction_rollback_before_apply(tmp_path,config):
    l=registered(tmp_path,config)
    before=l.snapshot()['runs'][0]['session']
    with pytest.raises(RuntimeError):
        with l.transaction() as db:
            db.execute("UPDATE runs SET session='damaged'")
            raise RuntimeError('crash')
    assert Ledger(l.path).snapshot()['runs'][0]['session']==before


def test_concurrent_processes_one_global_inflight(tmp_path,config):
    l=registered(tmp_path,config)
    code='from adfl.budget.ledger import Ledger; import sys; from adfl.budget.guard import BudgetStop\nl=Ledger(sys.argv[1])\ntry: l.reserve("g1-01",sys.argv[2],1,1000,{}); print("ok")\nexcept Exception: print("blocked")'
    env={**os.environ,'PYTHONPATH':str(Path('src').resolve())}
    def call(_):
        return subprocess.run([sys.executable,'-c',code,str(l.path),fingerprint(config)],env=env,capture_output=True,text=True,check=True).stdout.strip()
    with ThreadPoolExecutor(2) as pool: outcomes=list(pool.map(call,range(2)))
    assert sorted(outcomes)==['blocked','ok'] and Ledger(l.path).snapshot()['exposure_micro_cny']==1000


@pytest.mark.parametrize('amount',[8000001,10000000,90000000,100000000])
def test_persistent_budget_limits(tmp_path,config,amount):
    l=registered(tmp_path,config)
    with pytest.raises(BudgetStop): l.reserve('g1-01',fingerprint(config),1,amount,{})
    assert l.snapshot()['exposure_micro_cny']==0


@pytest.mark.parametrize('mode',['timeout','missing-usage','cache-unknown','truncated','bad-arguments','wrong-model','too-many-actions'])
def test_every_failure_preserved_no_retry(tmp_path,config,mode):
    l=registered(tmp_path,config); calls=[]
    def transport(*a,**k):
        calls.append(1)
        r=response({'kind':'wait'})
        if mode=='timeout': raise TimeoutError('test timeout')
        if mode=='missing-usage': r['body'].pop('usage')
        if mode=='cache-unknown': r['body']['usage'].pop('prompt_tokens_details')
        if mode=='truncated': r['body']['choices'][0]['finish_reason']='length'
        if mode=='bad-arguments': r['body']['choices'][0]['message']['tool_calls'][0]['function']['arguments']='{bad'
        if mode=='wrong-model': r['body']['model']='unexpected-fallback'
        if mode=='too-many-actions': r=response({'kind':'combo','actions':[{'kind':'wait'}]*13})
        return r
    try: Gate1Engine(l,config,transport).run('g1-01')
    except BudgetStop: pass
    s=Ledger(l.path).snapshot()
    assert len(calls)==1 and len(s['requests'])==1 and s['requests'][0]['response']
    assert s['exposure_micro_cny']>0 and s['requests'][0]['billed'] is None
    assert s['runs'][0]['status'] in {'failed','paused_unknown_cost'}
    export(l,config,'g1-01',tmp_path/'export')
    assert json.loads((tmp_path/'export/metrics.json').read_text())['actual_api_cost_cny'] is None


def test_decision_limit_and_no_automatic_next_run(tmp_path,config):
    l=registered(tmp_path,config); calls=[]
    def transport(*a,**k): calls.append(1); return response({'kind':'wait'})
    s=Gate1Engine(l,config,transport).run('g1-01')
    assert len(calls)==8 and s['runs'][0]['status']=='failed'
    l.register('g1-02',fingerprint(config),initial_session('attribution:E','p1'))
    with pytest.raises(BudgetStop): l.approve('g1-02',fingerprint(config),'premature',ready=True,predecessor='g1-01')
    assert len(calls)==8


def test_fingerprint_change_and_bill_mismatch_block(tmp_path,config):
    l=registered(tmp_path,config)
    with pytest.raises(BudgetStop): l.reserve('g1-01','changed',1,1000,{})
    req=l.reserve('g1-01',fingerprint(config),1,1000,{})
    u={'input_tokens':100,'output_tokens':20,'cached_tokens':0,'cache_write_tokens':0}
    l.receive(req,response({'kind':'wait'}),u,50)
    with pytest.raises(BudgetStop): l.reconcile(req,500,u,'mismatch')
    assert Ledger(l.path).snapshot()['requests'][0]['billed']==500
    assert Ledger(l.path).snapshot()['requests'][0]['status']=='billing_mismatch'


def test_redaction_and_gt_separation():
    assert redact({'authorization':'private','body':'sk-synthetic'})=={'authorization':'[REDACTED]','body':'[REDACTED]'}
    s=initial_session('attribution:H','p1')
    assert 'root_cause' not in json.dumps(s['messages'])


def test_crash_after_tool_effect_before_commit_replays_once(tmp_path,config,monkeypatch):
    l=registered(tmp_path,config); calls=[]
    real_apply=l.apply
    def crashed(*args,**kwargs): raise RuntimeError('simulated process interruption before atomic commit')
    monkeypatch.setattr(l,'apply',crashed)
    def transport(*a,**k):
        calls.append(1)
        return response({'kind':'combo','actions':[{'kind':'apply_change','target':'B'},{'kind':'verify'}]})
    with pytest.raises(RuntimeError): Gate1Engine(l,config,transport).run('g1-01')
    saved=json.loads(l.snapshot()['runs'][0]['session'])
    assert saved['decisions']==0 and saved['environment']['state']['history']==[]
    monkeypatch.setattr(l,'apply',real_apply)
    s=Gate1Engine(Ledger(l.path),config,transport).run('g1-01')
    assert len(calls)==1 and s['runs'][0]['status']=='completed'
    assert len(json.loads(s['runs'][0]['session'])['environment']['state']['history'])==2


def test_unknown_bill_manual_close_and_no_resend(tmp_path,config):
    l=registered(tmp_path,config)
    req=l.reserve('g1-01',fingerprint(config),1,1000,{})
    with pytest.raises(BudgetStop): l.reconcile(req,500,None,'bill before operator confirmed worker stopped')
    l.reconcile(req,500,None,'synthetic bill of crashed request',process_stopped=True)
    with pytest.raises(BudgetStop): l.close_uncertain('g1-01','no stopped confirmation')
    l.close_uncertain('g1-01','worker stopped; synthetic bill checked',process_stopped=True)
    l.review('g1-01','retain as failed trajectory')
    s=Ledger(l.path).snapshot()
    assert s['runs'][0]['status']=='failed' and s['exposure_micro_cny']==500
    assert s['requests'][0]['status']=='aborted'


def test_spend_does_not_reset_when_all_calls_settled(tmp_path,config):
    l=registered(tmp_path,config,spend_cap=8000000)
    req=l.reserve('g1-01',fingerprint(config),1,7999999,{})
    u={'input_tokens':100,'output_tokens':20,'cached_tokens':0,'cache_write_tokens':0}
    l.receive(req,response({'kind':'wait'}),u,7999999)
    s=json.loads(l.snapshot()['runs'][0]['session']); s['decisions']=1
    l.apply(req,s,{},terminal=False)
    l.reconcile(req,7999999,u,'synthetic near-cap bill')
    reopened=Ledger(l.path)
    with pytest.raises(BudgetStop): reopened.reserve('g1-01',fingerprint(config),2,2,{})
    assert reopened.snapshot()['actual_verified_micro_cny']==7999999


def test_absent_ledger_is_not_automatically_initialized(tmp_path):
    p=tmp_path/'absent.sqlite3'
    with pytest.raises(BudgetStop): Ledger(p)
    assert not p.exists()


def test_first_run_independent_cap_survives_restart(tmp_path,config):
    l=registered(tmp_path,config)
    req=l.reserve('g1-01',fingerprint(config),1,999999,{})
    u={'input_tokens':100,'output_tokens':20,'cached_tokens':0,'cache_write_tokens':0}
    l.receive(req,response({'kind':'wait'}),u,50)
    s=json.loads(l.snapshot()['runs'][0]['session']); s['decisions']=1
    l.apply(req,s,{},terminal=False)
    reopened=Ledger(l.path)
    with pytest.raises(BudgetStop,match='independent trajectory'): reopened.reserve('g1-01',fingerprint(config),2,2,{})
    assert reopened.snapshot()['exposure_micro_cny']==999999
    assert reopened.snapshot()['runs'][0]['spend_cap']==1000000


def test_first_run_report_actual_records_and_unknown_bill(tmp_path,config):
    l=registered(tmp_path,config)
    def transport(*a,**kw):
        return response({'kind':'combo','actions':[{'kind':'apply_change','target':'B'},{'kind':'verify'}]})
    Gate1Engine(l,config,transport).run('g1-01')
    p=tmp_path/'first.md'
    first_run_report(l,config,p)
    text=p.read_text(encoding='utf-8')
    assert 'qwen/qwen-flash' in text and '未知' in text and '决策 1' in text
    assert 'root_cause' not in text and '¥1.00' in text
    r=l.snapshot()['requests'][0]
    l.reconcile(r['id'],r['calculated'],json.loads(r['usage']),'synthetic bill')
    first_run_report(l,config,p)
    assert '未知（尚有请求未核对实际账单）' not in p.read_text(encoding='utf-8')


def test_confirmed_model_does_not_imply_model_permission(tmp_path,config):
    config['model_access_confirmed']=False
    l=registered(tmp_path,config); calls=[]
    with pytest.raises(BudgetStop): Gate1Engine(l,config,lambda *a,**kw:calls.append(1)).run('g1-01')
    assert not calls and 'model_access_confirmed' in readiness(config)['blockers']


def test_explicit_estimate_authorization_preserves_unknown_cost(tmp_path,config):
    config['estimate_based_first_run_authorized']=True
    config['usage_cache_semantics_confirmed']=False
    config['pricing']['cache_write_semantics']='unconfirmed'
    l=registered(tmp_path,config)
    def transport(*a,**kw):
        r=response({'kind':'combo','actions':[{'kind':'apply_change','target':'B'},{'kind':'verify'}]})
        r['body']['usage'].pop('prompt_tokens_details')
        return r
    s=Gate1Engine(l,config,transport).run('g1-01')
    assert s['runs'][0]['status']=='completed'
    r=s['requests'][0]
    assert r['billed'] is None and r['calculated'] is None
    assert json.loads(r['usage'])['cached_tokens'] is None
    assert s['exposure_micro_cny']==r['reserved']>0
    with pytest.raises(BudgetStop,match='restricted to g1-01'):
        Gate1Engine(l,config,transport).run('g1-02')


def test_estimate_mode_still_stops_missing_primary_usage(tmp_path,config):
    config['estimate_based_first_run_authorized']=True
    l=registered(tmp_path,config); calls=[]
    def transport(*a,**kw):
        calls.append(1); return response({'kind':'wait'},usage={})
    with pytest.raises(BudgetStop): Gate1Engine(l,config,transport).run('g1-01')
    assert len(calls)==1 and l.snapshot()['runs'][0]['status']=='paused_unknown_cost'


def test_observed_provider_tool_with_stop_is_rejected_without_execution():
    # Characterize g1-01 without changing frozen protocol or issuing a request.
    r=response({'kind':'diagnose','target':'A'})
    r['body']['choices'][0]['finish_reason']='stop'
    with pytest.raises(ValueError,match='completed native tool call'):
        decode_tool(r['body'],'qwen/qwen-flash',12)
