"""Pre-registered minimum Gate 2 contrasts, not new Agent algorithms."""
import copy
import json
import random
from adfl.agents.tools import TOOL_PROMPT
from adfl.world.pilot import PilotWorld

P1_ARMS=['no_intervention','reflection','oracle_attribution']
P5_ARMS=['belief_only','full_replan','selective_repair','oracle_dependency']
P1_RULES=('Two explanations for the prior unsuccessful A command are possible: unsuitable configuration or missing execution. '
          'inspect reports service status; diagnose A checks command delivery receipt; diagnose B tests whether A is compatible. '
          'apply_change A/B submits a configuration, verify checks restoration. Other tools have their usual CDW meaning.')
P5_RULES=('Task actions and node mapping: prepare creates shared snapshot; calibrate validates shared credentials; '
          'inspect A/B stages that configuration and inspects it (requires snapshot and credentials); '
          'apply_change A/B deploys it (requires matching staging and current requirement); diagnose A/B performs and registers its smoke test (requires matching applied change); '
          'verify completes service verification (requires applied current configuration and its smoke test). '
          'All primitive actions cost one, including redundant shared work. Old DAG: snapshot and credentials -> stage:A -> apply:A -> smoke:A -> verify:A. '
          'Completed nodes: snapshot, credentials, stage:A. Pending old actions: apply_change A, diagnose A, verify. '
          'The old plan is historical, not an instruction overriding new evidence.')


def session_for(line, arm, truth='H'):
    w=PilotWorld(); obs=w.reset(('ambiguous' if line=='p1' else 'dependency')+':'+truth,0)
    cp=w.snapshot()
    messages=[{'role':'system','content':TOOL_PROMPT+' '+(P1_RULES if line=='p1' else P5_RULES)},
              {'role':'user','content':json.dumps(obs)}]
    if line=='p1':
        interventions={'no_intervention':None,
            'reflection':'Reflect on the unsuccessful attempt, consider competing explanations, and choose your next action. No additional evidence is provided.',
            'oracle_attribution':'Privileged evaluator attribution: '+('hypothesis error; the prior command executed but its configuration is incompatible.' if truth=='H' else 'execution error; the prior configuration is compatible but its command did not execute.')}
    else:
        fact='New verified requirement: configuration B is required; the shared snapshot and credentials remain valid.'
        interventions={'belief_only':fact,
            'full_replan':fact+' Discard the old plan as a plan and construct a complete new plan from the goal, checking all prerequisites. Do not assume that discarding a plan erases valid environment state.',
            'selective_repair':fact+' Repair only the steps whose prerequisites or effects are invalidated by this evidence; retain valid completed steps and dependencies.',
            'oracle_dependency':fact+' Privileged evaluator dependency hint: invalid old nodes are stage:A, apply:A, smoke:A, verify:A. Valid completed nodes are snapshot and credentials. Replace only invalid target-specific nodes with their B counterparts.'}
    instruction=interventions[arm]
    if instruction:
        messages.append({'role':'user','content':instruction})
    return {'task_id':w.s['task_id'],'line':line,'source':'SIM' if arm=='no_intervention' else 'CF' if 'oracle' not in arm else 'ORACLE',
        'environment_origin':'SIM','split':'pilot','condition':arm,'seed':0,'decisions':0,
        'checkpoint_hash':w.checkpoint_hash(),'initial':cp,'environment':copy.deepcopy(cp),
        'messages':messages,'intervention':instruction,'error':None}


def ordered_runs():
    runs=[('g2-p1-'+a,'p1',a) for a in P1_ARMS]+[('g2-p5-'+a,'p5',a) for a in P5_ARMS]
    random.Random(0).shuffle(runs)
    return runs


def channel_pair(base_messages, fact):
    """Legal matched native-tool scaffold; only placement of the same fact changes.

    Both arms have the same call, two result messages and content multiset.
    This is a prepared fixture, not an assertion of naturally obtained tool evidence.
    """
    call={'role':'assistant','content':None,'tool_calls':[{'id':'paired-fact','type':'function',
        'function':{'name':'cdw_action','arguments':json.dumps({'action':{'kind':'diagnose','target':'B'}})}}]}
    neutral='No additional information.'
    result={}
    for carrier in ('user','tool'):
        result[carrier]=copy.deepcopy(base_messages)+[copy.deepcopy(call),
            {'role':'tool','tool_call_id':'paired-fact','content':fact if carrier=='tool' else neutral},
            {'role':'user','content':fact if carrier=='user' else neutral}]
    return result
