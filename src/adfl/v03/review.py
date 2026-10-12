"""Freeze or verify a review artifact. Intentionally cannot approve or run models."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from adfl.budget.pricing import RateCard
from adfl.v03.stage_a import SPLITS, ledger_audit
from adfl.v03.world import digest
from adfl.v03.design import PROMPT_VERSION, TOOL, PROMPT

MODELS=('google/gemini-3.8-flash','anthropic/claude-sonnet-5.5')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def costs(root):
    catalog=json.loads((root/'research/provider/v03/models.json').read_text(encoding='utf-8'))
    fx=json.loads((root/'research/provider/ecb-fx.json').read_text(encoding='utf-8'))
    result=[]
    for model_id in MODELS:
        model=next(m for m in catalog['data'] if m['id']==model_id)
        prices=model['pricing']; mul=Decimal(1000000)
        rates={k:str(Decimal(v)*mul) for k,v in prices.items() if k in {'prompt','completion','input_cache_read'} or k.startswith('input_cache_write')}
        writes=[Decimal(v) for k,v in rates.items() if k.startswith('input_cache_write')]
        card=dict(currency='USD',input=rates['prompt'],output=rates['completion'],cache_read=rates['input_cache_read'],
            cache_write=str(max(writes)),cny_per_usd=fx['cny_per_usd'],cache_write_semantics='unconfirmed')
        bound=RateCard(card).reserve(4096,512)
        uncached=(Decimal(4096)*Decimal(card['input'])+Decimal(512)*Decimal(card['output']))/mul*Decimal(card['cny_per_usd'])*8
        result.append(dict(id=model_id,metadata=model,usd_per_million=rates,conservative_ratecard=card,
            request_reserve_micro_cny=bound,trajectory_reserve_micro_cny=bound*8,
            assumptions=dict(max_decisions=8,max_input_tokens_per_request=4096,max_output_tokens=512,
                cache_discount=False,contingency=2,account_tariff_verified=False),
            counts={str(n):dict(uncached_reference_cny=str(uncached*n),conservative_reserve_cny=str(Decimal(bound*8*n)/mul))
                    for n in (2,4,6,12)}))
    return result


def build(root):
    manifest=[json.loads(x) for x in (root/'research/V03_TASK_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
    def arm(run,line,family,condition):
        row=next(r for r in manifest if r['line']==line and r['scenario_family']==f'{line}-{family}' and r['split']=='dev' and r['seed']==10)
        return dict(run_id=run,task_id=row['task_id'],condition=condition,checkpoint=row['checkpoint'],
                    checkpoint_sha256=row['checkpoint_sha256'])
    source_paths=sorted((root/'src/adfl').rglob('*.py'))+[root/'experiments/v03_alfworld_smoke.py']
    file_hashes={p.relative_to(root).as_posix():sha(p) for p in source_paths}
    for p in ('research/V03_TASK_MANIFEST.jsonl','research/provider/v03/models.json','research/provider/ecb-fx.json',
              'results/v03/stageA/tool_schema.json','results/v03/stageA/prompt.json',
              'research/V03_SCIENTIFIC_PROTOCOL.md','research/V03_LITERATURE_ASSET_GAPS.md',
              'research/V03_FRONTIER_MODEL_OPTIONS.md','research/V03_SOURCE_PROVENANCE.json','tests/test_v03_mechanisms.py'):
        file_hashes[p]=sha(root/p)
    estimate=costs(root)
    return dict(protocol='V0.3-StageA-1',status='FROZEN_FOR_REVIEW_NOT_APPROVED',paid_execution_authorized=False,
        created_date='2026-10-12',base_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        code_identity='base commit + exact file hashes; a reviewed final code commit required before paid approval',file_hashes=file_hashes,
        splits=SPLITS,selection_rule='first dev seed 10, preselected H/E pair and P5 B; no frontier outcome observed; holdout untouched',
        task_generation='World VERSION v03-world-1 / POMDP v03-pomdp-1; deterministic seed mapping; P5 common DAG with three update mechanisms',
        proposed_primary_model=MODELS[0],secondary_model=MODELS[1],model_revision='catalog canonical slug; immutable weights UNKNOWN',
        base_url='https://api.ofox.ai/v1',endpoint='/chat/completions',temperature=0,max_tokens=512,
        reasoning=dict(proposed_level='low',provider_wire_mapping=None,status='BLOCKING: verify OFox mapping and reasoning token accounting before approval'),
        max_decisions=8,max_primitive=12,input_token_bound=4096,prompt_version=PROMPT_VERSION,
        prompt_sha256=digest(PROMPT),tool_schema_sha256=digest(TOOL),
        visible_context='design.context()/intervention() only; checkpoint/manifest/evaluator truth prohibited',
        arms=[arm('v03-p1-h-natural','P1','H','no_intervention'),arm('v03-p1-e-natural','P1','E','no_intervention'),
              arm('v03-p5-b-belief','P5','B','belief_only'),arm('v03-p5-b-selective','P5','B','selective_dependency_repair')],
        execution_order=['v03-p1-h-natural','v03-p1-e-natural','v03-p5-b-selective','v03-p5-b-belief'],
        fairness='P1 H/E identical public context. P5 same snapshot, model, schema and caps; intervention wording only. Token consumption charged, not artificially equalized.',
        first_trajectory_review_required=True,secondary_family_requires_separate_approval=True,
        budget=dict(proposed_batch_cap_cny=8,gate2_cumulative_cap_cny=40,project_cap_cny=100,project_stop_cny=90,
            per_trajectory_proposed_cap_cny=2,prior_ledger=ledger_audit(root/'.state/gate1.sqlite3'),
            model_cost_estimates=estimate,known_unknowns=['account tariff','cache write/TTL/storage units','reasoning cap and accounting','settlement FX','per-request bills']),
        primary_outcomes=['task_success','tool_cost','net_utility = success - 0.05 * primitive calls'],
        secondary_outcomes=['P1 diagnostic choices and wrong-target modifications','P5 valid-work-retention','P5 obsolete-action-execution',
                            'P5 unnecessary-reexecution','P5 plan-consistency'],
        statuses=['SUCCESS','AGENT_TASK_FAIL','HARNESS_FAIL','BUDGET_TRUNCATION','UNIDENTIFIABLE'],
        exclusions='None silently. Retain every candidate/run/error in denominator with cause; no retries, rerun selection, model fallback or prompt repair.',
        stop_rules=['No paid calls before explicit approval bound to this hash and final reviewed code commit',
            'Unknown tariffs beyond estimate: stop, do not assume zero','Unknown bills retain full reservations',
            'First-run review before continuation','Any schema/transport/model mismatch: preserve and pause',
            'No tuning after frontier outcome; saturation/negative findings retained'],
        deferred=['P1 reflection/diagnostic/oracle paid arms','P2/P3 paid arms','P4 new algorithms','P5 full-replan/oracle paid arms',
                  'ALFWorld OBS trajectories','new V03 paid runner binding versioned schema to existing transport/ledger'])


def verify(root):
    p=root/'research/V03_PREREGISTRATION.json'
    expected=(root/'research/V03_PREREGISTRATION.sha256').read_text(encoding='utf-8').split()[0]
    if sha(p)!=expected:
        raise ValueError('preregistration SHA256 changed')
    value=json.loads(p.read_text(encoding='utf-8'))
    for path,expected_hash in value['file_hashes'].items():
        if sha(root/path)!=expected_hash:
            raise ValueError('frozen file changed: '+path)
    for arm in value['arms']:
        cp=json.loads((root/arm['checkpoint']).read_text(encoding='utf-8'))
        if digest(cp)!=arm['checkpoint_sha256']:
            raise ValueError('checkpoint changed')
    current=ledger_audit(root/'.state/gate1.sqlite3')
    if current!=value['budget']['prior_ledger']:
        raise ValueError('ledger changed: re-audit and obtain a new scoped approval; never reset')
    return dict(frozen_artifacts_valid=True,preregistration_sha256=sha(p),paid_execution_authorized=False,
                blockers=value['budget']['known_unknowns']+[value['reasoning']['status'],'V03 paid runner not implemented'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',default='.')
    p.add_argument('--freeze',action='store_true',help='exclusive create; existing registration is never overwritten')
    a=p.parse_args(); root=Path(a.root).resolve()
    if a.freeze:
        target=root/'research/V03_PREREGISTRATION.json'; payload=build(root)
        with target.open('x',encoding='utf-8') as f:
            json.dump(payload,f,ensure_ascii=False,indent=2); f.write('\n')
        with (root/'research/V03_PREREGISTRATION.sha256').open('x',encoding='utf-8') as f:
            f.write(sha(target)+'  V03_PREREGISTRATION.json\n')
        print(json.dumps({'frozen':True,'sha256':sha(target)},indent=2))
    else:
        print(json.dumps(verify(root),ensure_ascii=True,indent=2))
