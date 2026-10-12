"""Local offline audit/fixture generator. No provider/transport import or API key access."""
import argparse
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from adfl.v03.world import World, digest, shortest_success
from adfl.v03.design import context, scripted, role_contexts, P3_CONDITIONS, TOOL, PROMPT, PROMPT_VERSION
from adfl.v03.pomdp import report as p4_report, BeliefSession

SPLITS = {'design':[0,1,2], 'dev':[10,11,12], 'holdout':[1000,1001,1002]}


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def old_artifacts(root):
    files = [p for p in (root/'results').rglob('*') if p.is_file() and 'v03' not in p.parts]
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def ledger_audit(path):
    """Read-only connection; no migrations, releases, or approval insertion."""
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        rows = db.execute('SELECT id,run,step,reserved,calculated,billed,status FROM requests ORDER BY id').fetchall()
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        # Hash content, omit raw rows/request bodies from public audit (data minimization).
        logical = {table:db.execute('SELECT * FROM "'+table.replace('"','""')+'" ORDER BY rowid').fetchall() for table in tables}
        return dict(requests=len(rows), unsettled=sum(r[5] is None for r in rows),
            exposure_micro_cny=sum(r[3] if r[5] is None else r[5] for r in rows),
            requests_summary_hash=digest(rows), all_tables_hash=digest(logical),
            disposition='Every unknown bill retains its full reservation. No aggregate balance allocation.')
    finally:
        db.close()


def generate(root):
    root = Path(root); out = root/'results/v03/stageA'; out.mkdir(parents=True,exist_ok=True)
    before = old_artifacts(root); ledger_before = ledger_audit(root/'.state/gate1.sqlite3')
    families = {'P1':['H','E','O','U'],'P2':['H','E'],'P3':list(P3_CONDITIONS),'P5':['A','B','C']}
    manifest = []; checks = []; rollouts = []
    for split,seeds in SPLITS.items():
        for line,fs in families.items():
            for family in fs:
                for seed in seeds:
                    task = f'v03-{line}-{family}-{seed}'
                    w = World(line,family,seed); snap = w.snapshot()
                    path = out/'evaluator_only/checkpoints'/f'{task}.json'; write(path,snap)
                    visible = context(w); visible_path = out/'visible'/f'{task}.json'; write(visible_path,visible)
                    groups = (['no_intervention','generic_reflection','diagnostic_evidence','oracle_failure_class'] if line == 'P1'
                        else ['C0','C1','C2'] if line == 'P2' else P3_CONDITIONS[family] if line == 'P3'
                        else ['belief_only','full_replan','selective_dependency_repair','oracle_dependency'])
                    manifest.append(dict(task_id=task,scenario_family=f'{line}-{family}',line=line,split=split,seed=seed,
                        checkpoint=path.relative_to(root).as_posix(),checkpoint_sha256=digest(snap),
                        visible_context=visible_path.relative_to(root).as_posix(),
                        gt_permission='evaluator_only; never pass checkpoint, task_id/family or this manifest to LLM',
                        conditions=groups, remaining_primitive=w.s['remaining'], provenance='SIM constructed fixture; not OBS benchmark'))
                    if split == 'holdout':
                        continue  # Freeze only, no holdout rollouts/selection.
                    restored = World.restore(snap)
                    assert restored.snapshot() == snap and restored.observe() == w.observe()
                    for a in w.actions():
                        c1,c2 = World.restore(snap),World.restore(snap)
                        assert c1.step(a) == c2.step(a) and c1.snapshot() == c2.snapshot()
                    oracle = shortest_success(w,8)
                    expected = not (line == 'P3' and family == 'irrecoverable')
                    assert oracle['feasible'] == expected
                    checks.append(dict(task=task,checkpoint_restore=True,all_one_step_forks_identical=True,
                        public_keys=list(w.observe()),oracle=oracle))
                    if oracle['feasible']:
                        rollouts.append(dict(task=task,condition='privileged exhaustive plan -> Scripted Mock',
                            result=scripted(World.restore(snap),oracle['actions'])))
    for seed in (0,1):
        assert context(World('P1','H',seed)) == context(World('P1','E',seed))
    u1,u2 = World('P1','U',0),World('P1','U',2)
    assert context(u1) == context(u2) and u1.s['hidden']['target'] != u2.s['hidden']['target']
    role_checks = []
    for seed in (0,1):
        for unreliable in (False,True):
            design = role_contexts(World('P2','H',seed),unreliable)
            h = design['histories']
            assert h['C1'][-1]['content'] == h['C2'][-2]['content'] == design['fact']
            role_checks.append(dict(seed=seed,unreliable=unreliable,design=design))
    write(out/'p2_native_histories.json',role_checks)
    p3 = []
    sequences = {'recoverable':{
        'continue':['wait','verify'],'generic_warning':['probe','advance','advance','verify'],
        'selective_repair':['advance','advance','verify']},
        'fragile_success':{'continue':['wait','verify'],'rollback':['rollback','advance','advance','verify'],
                           'wait_one_observation':['wait','verify']},
        'irrecoverable':{'continue':['advance'],'diagnostic_probe':['probe'],'selective_repair':['advance']}}
    for family,groups in sequences.items():
        for condition,seq in groups.items():
            w = World('P3',family)
            p3.append(dict(family=family,condition=condition,checkpoint_sha256=digest(w.snapshot()),
                result=scripted(w,[dict(kind=k) for k in seq])))
    write(out/'p3_mock_pairs.json',p3)
    action_values = []
    for family in P3_CONDITIONS:
        w = World('P3',family)
        for action in w.actions():
            branch = World.restore(w.snapshot()); branch.step(action)
            continuation = shortest_success(branch)
            # Best post-action utility allows stopping if no successful continuation exists.
            value = 1-0.05*(1+len(continuation['actions'])) if continuation['feasible'] else -0.05
            action_values.append(dict(family=family,first_action=action,best_net_utility=value,
                oracle_continuation=continuation,privileged=True))
    write(out/'p3_exact_action_values.json',action_values)
    p5 = []
    for family in ('A','B','C'):
        cp = World('P5',family).snapshot()
        w = World.restore(cp); oracle = shortest_success(w,8)
        old_tail=[dict(kind='execute_node',node=n) for n in ('merge','publish')]+[dict(kind='verify')]
        probe=World.restore(cp); probe.step(old_tail[0])
        resumed = old_tail if not probe.s['history'][-1]['invalid'] else [old_tail[0]]+oracle['actions']
        plans = {'old_tail_then_privileged_recovery':resumed,
                 'full_redo_work':[dict(kind='execute_node',node=n) for n in ('snapshot','credentials','left','right','merge','publish')]+[dict(kind='verify')],
                 'exact_selective':oracle['actions']}
        for label,plan in plans.items():
            p5.append(dict(family=family,scripted_policy=label,checkpoint_sha256=digest(cp),
                result=scripted(World.restore(cp),plan)))
    write(out/'p5_mock_contrasts.json',p5)
    for family in ('A','B','C','D'):
        for split,seeds in SPLITS.items():
            for seed in seeds:
                session = BeliefSession(family,seed)
                cp = session.snapshot()
                path = out/'evaluator_only/checkpoints'/f'v03-P4-{family}-{seed}.json'
                write(path,cp)
                manifest.append(dict(task_id=f'v03-P4-{family}-{seed}',scenario_family=f'P4-{family}',line='P4',split=split,
                    seed=seed,checkpoint=path.relative_to(root).as_posix(),checkpoint_sha256=digest(cp),
                    gt_permission='probability model public; sampled realized state evaluator_only',
                    conditions=['immediate','information_gain','lookahead2','exact'], provenance='SIM exact finite POMDP'))
    write(out/'p4_exact.json',p4_report())
    write(out/'tool_schema.json',TOOL); write(out/'prompt.json',dict(version=PROMPT_VERSION,prompt=PROMPT))
    write(out/'truth_restore_checks.json',checks); write(out/'mock_oracle_rollouts.json',rollouts)
    manifest_path = root/'research/V03_TASK_MANIFEST.jsonl'
    manifest_path.write_text(''.join(json.dumps(m,ensure_ascii=False,sort_keys=True)+'\n' for m in manifest),encoding='utf-8')
    after = old_artifacts(root); ledger_after = ledger_audit(root/'.state/gate1.sqlite3')
    assert before == after and ledger_before == ledger_after
    write(out/'preservation_audit.json',dict(old_artifact_count=len(before),old_artifact_hashes=before,
        unchanged=True,ledger_before=ledger_before,ledger_after=ledger_after,paid_model_calls=0,new_model_spend_cny=0,
        holdout='Generated/frozen checkpoints only; no rollouts, scoring or task selection on holdout.',
        manifest_rows=len(manifest),verified_nonholdout_worlds=len(checks),
        alfworld_installed=importlib.util.find_spec('alfworld') is not None))
    return dict(manifest_rows=len(manifest),verified_worlds=len(checks),rollouts=len(rollouts),
        ledger_exposure_cny=ledger_before['exposure_micro_cny']/1e6,old_artifacts_unchanged=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='.')
    args = parser.parse_args()
    print(json.dumps(generate(args.root),indent=2))
