"""Seven pre-registered CF/Oracle branches. No adaptive resampling or retry."""
import argparse
import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

from adfl.agents.tools import TOOLS, decode_tool
from adfl.agents.transport import OFoxTransport
from adfl.budget.guard import BudgetStop
from adfl.budget.ledger import Ledger
from adfl.budget.pricing import RateCard, usage_from
from adfl.gate1 import ROOT, LEDGER_PATH, fingerprint, export, digest
from adfl.pilot_design import ordered_runs, session_for
from adfl.world.pilot import PilotWorld


def config():
    c=json.loads((ROOT/'configs/gate1.json').read_text(encoding='utf-8'))
    c.update(gate=2,stage_cap_cny=40,batch_cap_cny=5,input_token_bound=32768,
        world_version='gate2-pilot-v1',prompt_version='gate2-paired-v1',
        batch_id='gate2-p1-p5-v1',run_order=ordered_runs())
    c['prompt_manifest']={rid:session_for(line,arm)['messages'] for rid,line,arm in ordered_runs()}
    c['base_prompt_hash']=c.pop('prompt_hash')
    c['prompt_hash']=digest(c['prompt_manifest'])
    return c


def check_config(c):
    for key,value in {'model_id':'qwen/qwen-flash','temperature':0,'max_tokens':512,'max_decisions':8,
                      'primitive_budget':12,'automatic_retries':0,'seed':0,'concurrency':1,
                      'input_token_bound':32768,'stage_cap_cny':40,'batch_cap_cny':5}.items():
        if c.get(key)!=value:
            raise BudgetStop('unfrozen pilot setting: '+key)
    if c['run_order']!=[list(r) for r in ordered_runs()] and c['run_order']!=ordered_runs():
        raise BudgetStop('unregistered branch/order')


class PilotEngine:
    def __init__(self, ledger, c, transport=None):
        check_config(c)
        self.ledger,self.c,self.fp=ledger,c,fingerprint(c)
        self.rates=RateCard(c['pricing']); self.transport=transport or OFoxTransport(c['base_url'])

    def run(self,rid):
        if rid not in {r[0] for r in self.c['run_order']}:
            raise BudgetStop('outside authorized pilot')
        while True:
            snap=self.ledger.snapshot(rid); run=snap['runs'][0]
            if run['fingerprint']!=self.fp or not run['approval']:
                raise BudgetStop('frozen pilot approval required')
            if run['status'] in {'completed','failed'}:
                return snap
            session=json.loads(run['session']); w=PilotWorld(); w.restore(session['environment'])
            pending=[r for r in snap['requests'] if r['status'] in {'reserved','received','ambiguous','billing_mismatch'}]
            if pending and pending[-1]['status']!='received':
                raise BudgetStop('uncertain request retained; no resend')
            if pending:
                request=pending[-1]; response=json.loads(request['response'])
            else:
                payload={'model':self.c['model_id'],'temperature':0,'max_tokens':512,'stream':False,
                    'messages':session['messages'],'tools':TOOLS,'tool_choice':{'type':'function','function':{'name':'cdw_action'}}}
                if len(json.dumps(payload,ensure_ascii=False).encode())+1024>self.c['input_token_bound']:
                    raise BudgetStop('input bound exceeded; no truncation')
                req=self.ledger.reserve(rid,self.fp,session['decisions']+1,self.rates.reserve(self.c['input_token_bound'],512),payload)
                start=time.perf_counter()
                try:
                    response=self.transport(payload,send_authorized=True)
                except Exception as exc:
                    response={'status':None,'body':None,'transport_error':type(exc).__name__}
                response['latency_s']=time.perf_counter()-start
                usage=calculated=None; error=None
                try:
                    usage=usage_from(response.get('body'))
                    if usage['input_tokens']>self.c['input_token_bound'] or usage['output_tokens']>512:
                        raise BudgetStop('usage exceeds reservation bounds')
                    calculated=self.rates.calculated(usage)
                except Exception as exc:
                    error=type(exc).__name__+': '+str(exc)
                response['cost_error']=error
                self.ledger.receive(req,response,usage,calculated,valid=error is None,allow_estimate=True)
                request=self.ledger.snapshot(rid)['requests'][-1]
                if request['status']!='received':
                    raise BudgetStop('unknown primary usage/transport cost; reservation retained')
            before=w.get_observation(); decision=None; error=None
            try:
                if response.get('status')!=200:
                    raise ValueError('HTTP failure: '+str(response.get('status')))
                message,call_id,decision=decode_tool(response['body'],self.c['model_id'],w.s['remaining_budget'])
                result=w.step(decision['action'])
                session['messages'].extend([message,{'role':'tool','tool_call_id':call_id,'content':json.dumps(result)}])
            except Exception as exc:
                error=type(exc).__name__+': '+str(exc); result=w.get_observation()
            session['decisions']+=1
            terminal=bool(w.score()['success'] or session['decisions']>=8 or w.s['remaining_budget']<=0 or error)
            if terminal and not w.score()['success'] and not error:
                error='decision/action budget exhausted'
            session.update(environment=w.snapshot(),error=error)
            trajectory={'step':session['decisions'],'visible_before':before,'action':decision.get('action') if decision else None,
                'tool_result':result,'belief_report':decision.get('belief') if decision else None,
                'plan_snapshot':decision.get('plan') if decision else None,'messages':session['messages'],
                'usage':json.loads(request['usage']),'calculated_micro_cny':request['calculated'],'actual_billed_cny':None,
                'compatibility_anomaly':'native_tool_call_with_finish_reason_stop' if decision and not error and response['body']['choices'][0]['finish_reason']=='stop' else None,
                'latency_s':response.get('latency_s'),'error':error}
            self.ledger.apply(request['id'],session,trajectory,terminal=terminal,error=error)
            if terminal:
                return self.ledger.snapshot(rid)


def prepare():
    destination=ROOT/'results/gate2'; path=destination/'preregistration.json'
    if path.exists():
        raise BudgetStop('pilot already registered; do not overwrite')
    destination.mkdir(exist_ok=True)
    ledger=Ledger(LEDGER_PATH)
    before=ledger.snapshot()
    # Preserve original artifacts and ledger before any additive migration.
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'results/gate1').rglob('*') if p.is_file()}
    (destination/'gate1-preservation.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    backup=ROOT/'.state/backups/gate1-before-gate2.sqlite3'
    if backup.exists():
        raise BudgetStop('backup already exists')
    with sqlite3.connect(LEDGER_PATH) as src, sqlite3.connect(backup) as target:
        src.backup(target)
    c=config(); check_config(c)
    with urllib.request.urlopen('https://api.ofox.ai/v1/models',timeout=30) as r:
        catalog=json.loads(r.read())
    model=next(m for m in catalog['data'] if m['id']==c['model_id'])
    prior=json.loads((ROOT/c['catalog_path']).read_text(encoding='utf-8'))
    previous=next(m for m in prior['data'] if m['id']==c['model_id'])
    if model['pricing']!=previous['pricing'] or not {'tools','tool_choice','temperature','max_tokens'}.issubset(model['supported_parameters']):
        raise BudgetStop('pricing/capability changed; review before inference')
    c['public_model_preflight']=model
    path.write_text(json.dumps(c,indent=2),encoding='utf-8')
    fp=fingerprint(c)
    for rid,line,arm in ordered_runs():
        ledger.register(rid,fp,session_for(line,arm),spend_cap=1000000)
    evidence='User authorized only minimum P1/P5 paired Gate 2 pilot after Mock checks, CNY5 pilot cap/CNY40 cumulative/CNY100 project, preserved prior unknown reservations, no retries or adaptive complexity.'
    ledger.authorize_pilot(c['batch_id'],[r[0] for r in ordered_runs()],fp,evidence)
    print(json.dumps({'order':ordered_runs(),'prior_exposure_cny':before['exposure_micro_cny']/1e6,
        'max_batch_reservation_cny':RateCard(c['pricing']).reserve(32768,512)*56/1e6,'fingerprint':fp}))


def run(rid):
    c=json.loads((ROOT/'results/gate2/preregistration.json').read_text(encoding='utf-8')); ledger=Ledger(LEDGER_PATH)
    ids=[r[0] for r in c['run_order']]
    if rid not in ids:
        raise BudgetStop('unknown pilot branch')
    for prev in ids[:ids.index(rid)]:
        run=ledger.snapshot(prev)['runs'][0]; session=json.loads(run['session'])
        if run['status'] not in {'completed','failed'} or session['error'] not in {None,'decision/action budget exhausted'}:
            raise BudgetStop('prior branch incomplete/interface error; stop batch')
    path=ROOT/'results/gate2'/rid
    try:
        PilotEngine(ledger,c).run(rid)
    finally:
        export(ledger,c,rid,path,world_type=PilotWorld)
    print((path/'metrics.json').read_text(encoding='utf-8'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['prepare','run']); parser.add_argument('--run-id')
    args=parser.parse_args()
    prepare() if args.command=='prepare' else run(args.run_id)
