"""Visible contexts and distinct interventions; no transport calls."""
import copy
import json

PROMPT_VERSION = 'v03-mechanisms-1'
PROMPT = ('Complete and verify the task using tools. Costs are one primitive per action; '
          'every observed failure remains in the record. Receipts, compatibility and sensor '
          'validity are distinct. Plan node execution uses current requirements, rejects '
          'invalid prerequisites, and changes its generation, invalidating dependent stamps. '
          'Do not assume every report is authoritative.')
SCHEMA = {'type':'object','oneOf':[
    {'type':'object','properties':{'kind':{'enum':['receipt','compatibility','audit_monitor','verify','wait',
        'advance','rollback','probe','audit']}},'required':['kind'],'additionalProperties':False},
    {'type':'object','properties':{'kind':{'const':'apply'},'target':{'enum':['A','B']}},
     'required':['kind','target'],'additionalProperties':False},
    {'type':'object','properties':{'kind':{'const':'execute_node'},'node':{'enum':[
        'snapshot','credentials','left','right','merge','publish']}},
     'required':['kind','node'],'additionalProperties':False}]}
TOOL = {'type':'function','function':{'name':'cdw_v03_action',
    'description':'Execute one versioned primitive action; only actions listed for this task are legal.',
    'parameters':SCHEMA}}


def context(world, condition='natural'):
    messages = [{'role':'system','content':PROMPT}, {'role':'user','content':json.dumps(
        {'task':'Restore/complete and verify', 'observation':world.observe(), 'actions':world.actions()},sort_keys=True)}]
    if condition in {'natural','no_intervention','belief_only','continue'}:
        pass
    elif condition == 'generic_reflection':
        messages.append({'role':'user','content':'Reconsider your current hypothesis and plan using the available evidence before continuing.'})
    elif condition == 'full_replan':
        messages.append({'role':'user','content':'Rebuild your plan from the current requirements. Decide yourself whether completed work remains valid; do not automatically redo it.'})
    elif condition == 'selective_dependency_repair':
        messages.append({'role':'user','content':'Check changed prerequisites and their dependent nodes. Retain valid completed work and repair only invalid dependencies before continuing.'})
    elif condition == 'oracle_failure_class':
        messages.append({'role':'user','content':'PRIVILEGED upper-bound label: '+world.s['family']})
    elif condition == 'oracle_dependency':
        invalid = [n for n in world.s['done'] if not world.valid(n)]
        messages.append({'role':'user','content':'PRIVILEGED evaluator live-invalid completed nodes: '+json.dumps(invalid)})
    else:
        raise ValueError(condition)
    return messages


def role_contexts(world, unreliable=False):
    """A real compatibility action is executed ONCE before all role branches.

    This is a delivery-channel manipulation, not an extra tool for C2. The raw
    receipt is preserved separately; a masking layer routes the same factual
    payload into user or native tool. C0 withholds it. All groups pay that prefix.
    """
    w = type(world).restore(world.snapshot())
    result = w.step({'kind':'compatibility'})
    fact = result['observation']
    if unreliable and world.s['seed'] % 5 == 0:
        fact = fact.replace('incompatible','TEMP').replace('compatible','incompatible').replace('TEMP','compatible')
    fact += ' Source reliability: ' + ('0.8 (separate unreliable subgroup).' if unreliable else '1.0 (authoritative).')
    # Mask the public last observation equally before role assignment.
    raw = w.snapshot(); w.s['last'] = 'Diagnostic completed; evidence delivery controlled by experimental channel.'
    base = context(world)  # Chronological initial observation precedes the actual prefix call.
    call = {'role':'assistant','content':None,'tool_calls':[{'id':'v03_fact_001','type':'function',
        'function':{'name':'cdw_v03_action','arguments':'{"kind":"compatibility"}'}}]}
    result_groups = {}
    neutral = 'Diagnostic completed; factual payload withheld from this channel.'
    for group in ('C0','C1','C2'):
        msgs = copy.deepcopy(base)+[copy.deepcopy(call)]
        msgs.append({'role':'tool','tool_call_id':'v03_fact_001',
                     'content':fact if group == 'C2' else neutral})
        msgs.append({'role':'user','content':fact if group == 'C1' else neutral})
        result_groups[group] = msgs
    return dict(checkpoint=w.snapshot(), raw_tool_checkpoint=raw, fact=fact, histories=result_groups,
                prefix_cost=1, manipulation='delivery filter; C1/C2 have identical fact string, different role scaffolding')


def intervention(world, condition):
    """Same pre-treatment checkpoint; real diagnostic costs remain in the budget."""
    w = type(world).restore(world.snapshot())
    if w.s['line']=='P3':
        if condition=='generic_warning':
            msgs=context(w); msgs.append({'role':'user','content':'Check whether the current course needs correction; avoid disrupting progress that can finish naturally.'})
            return w,msgs
        prefix={'diagnostic_probe':'probe','selective_repair':'advance',
                'rollback':'rollback','wait_one_observation':'wait'}.get(condition)
        if prefix:
            msgs=context(w); result=w.step({'kind':prefix})
            msgs += [{'role':'assistant','content':None,'tool_calls':[{'id':'v03_p3_prefix','type':'function',
                'function':{'name':'cdw_v03_action','arguments':json.dumps({'kind':prefix})}}]},
                {'role':'tool','tool_call_id':'v03_p3_prefix','content':json.dumps(result)}]
            return w,msgs
    if condition == 'diagnostic_evidence':
        messages = context(w)
        result = w.step({'kind':'receipt'})
        messages += [{'role':'assistant','content':None,'tool_calls':[{'id':'v03_diagnostic_001','type':'function',
            'function':{'name':'cdw_v03_action','arguments':'{"kind":"receipt"}'}}]},
            {'role':'tool','tool_call_id':'v03_diagnostic_001','content':json.dumps(result)}]
        return w,messages
    return w,context(w,condition)


P3_CONDITIONS = {'recoverable':['continue','generic_warning','selective_repair'],
                 'fragile_success':['continue','rollback','wait_one_observation'],
                 'irrecoverable':['continue','diagnostic_probe','selective_repair']}


def scripted(world, actions):
    from adfl.agents.interface import MockAgent
    agent = MockAgent(actions); messages = context(world); trace = []
    for _ in actions:
        if world.s['terminal'] or not world.s['remaining']:
            break
        action = agent.act(copy.deepcopy(messages))['action']; observation = world.step(action)
        trace.append({'action':action,'observation':observation})
        messages.append({'role':'assistant','content':json.dumps(action)})
        messages.append({'role':'user','content':json.dumps(observation)})
    return {'agent':'Scripted Mock; not an LLM experiment','trace':trace,'score':world.score()}
