"""Scripted instrument calibration; never scientific Agent performance evidence."""
import json
import tempfile
from pathlib import Path
from adfl.agents import MockAgent
from adfl.budget.ledger import Ledger
from adfl.gate1 import fingerprint, export
from adfl.gate2 import config, PilotEngine
from adfl.pilot_design import ordered_runs, session_for, channel_pair
from adfl.world.pilot import PilotWorld


def main():
    c=config(); fp=fingerprint(c); output=Path('results/gate2/mock'); output.mkdir(parents=True,exist_ok=True)
    suffix=[{'kind':'inspect','target':'B'},{'kind':'apply_change','target':'B'},{'kind':'diagnose','target':'B'},{'kind':'verify'}]
    scripts={
        'no_intervention':[{'kind':'apply_change','target':'A'}]+[{'kind':'verify'}]*7,
        'reflection':[{'kind':'diagnose','target':'A'},{'kind':'apply_change','target':'B'},{'kind':'verify'}],
        'oracle_attribution':[{'kind':'apply_change','target':'B'},{'kind':'verify'}],
        'belief_only':[{'kind':'apply_change','target':'A'},{'kind':'diagnose','target':'A'}]+[{'kind':'verify'}]*6,
        'full_replan':[{'kind':'prepare'},{'kind':'calibrate'}]+suffix,
        'selective_repair':suffix,'oracle_dependency':suffix}
    with tempfile.TemporaryDirectory() as d:
        ledger=Ledger(Path(d)/'mock.sqlite3',create=True)
        for rid,line,arm in ordered_runs(): ledger.register(rid,fp,session_for(line,arm),spend_cap=1000000)
        ledger.authorize_pilot(c['batch_id'],[r[0] for r in ordered_runs()],fp,'Mock calibration only; no real API authorization')
        for rid,line,arm in ordered_runs():
            agent=MockAgent(scripts[arm]); count=[0]
            def transport(payload,**kwargs):
                decision=agent.act(payload['messages']); count[0]+=1
                return {'status':200,'body':{'model':c['model_id'],'id':'synthetic-'+str(count[0]),
                    'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{
                    'id':'synthetic-call-'+str(count[0]),'type':'function','function':{'name':'cdw_action','arguments':json.dumps(decision)}}]}}],
                    'usage':{'prompt_tokens':300,'completion_tokens':30,'total_tokens':330}}}
            PilotEngine(ledger,c,transport).run(rid)
            export(ledger,c,rid,output/rid,world_type=PilotWorld)
        scores={rid:json.loads((output/rid/'metrics.json').read_text(encoding='utf-8')) for rid,_,_ in ordered_runs()}
    extra={}
    for truth in ('H','E'):
        w=PilotWorld(); w.reset('ambiguous:'+truth); cp=w.snapshot(); arms={}
        for arm,actions in {
            'no_intervention':[{'kind':'apply_change','target':'A'},{'kind':'verify'}],
            'fixed_reflection':[{'kind':'apply_change','target':'A'},{'kind':'verify'}],
            'diagnostic_intervention':[{'kind':'diagnose','target':'A'},{'kind':'apply_change','target':'B' if truth=='H' else 'A'},{'kind':'verify'}]}.items():
            w.restore(cp); observations=[w.step(a) for a in actions]
            messages=session_for('p1','reflection' if arm=='fixed_reflection' else 'no_intervention',truth)['messages']
            arms[arm]={'messages_before':messages,'intervention':'actual diagnose(A) action' if arm=='diagnostic_intervention' else 'fixed reflection message' if arm=='fixed_reflection' else None,
                       'actions':actions,'observations':observations,'score':w.score(),'checkpoint_hash':session_for('p1','no_intervention',truth)['checkpoint_hash']}
        extra['p3-'+truth]=arms
    pair=channel_pair(session_for('p5','belief_only')['messages'][:2],'Verified: configuration B is required; shared snapshot and credentials remain valid.')
    extra['p2-channel-pair']=pair
    w=PilotWorld(); w.reset('complementary:H')
    actions=[{'kind':'calibrate'},{'kind':'diagnose','target':'A'},{'kind':'diagnose','target':'B'},{'kind':'apply_change','target':'B'},{'kind':'verify'}]
    extra['p4-complementary']={'actions':actions,'observations':[w.step(a) for a in actions],'score':w.score()}
    (output/'summary.json').write_text(json.dumps({'scientific_evidence':False,'actual_api_calls':0,'actual_api_cost_cny':0,'scripts_chosen_by_evaluator':True,'scores':scores,'other_lines_offline_only':extra},indent=2),encoding='utf-8')
    print('Mock calibration artifacts exported; zero network calls.')


if __name__=='__main__': main()
