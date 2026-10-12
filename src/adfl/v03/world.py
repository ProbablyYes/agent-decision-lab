"""Finite, checkpointable mechanism worlds. Evaluator state is never an observation."""
import copy
import hashlib
import json
from collections import deque


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class World:
    VERSION = 'v03-world-1'

    def __init__(self, line, family, seed=0, budget=12):
        self.s = dict(version=self.VERSION, line=line, family=family, seed=seed,
                      rng_state={'algorithm':'deterministic seed mapping; no random draws','seed':seed},
                      primitive_cost=1, remaining=budget, history=[], success=False, terminal=False, last='')
        # Seeds permute labels, not difficulty. Split assignment is external and frozen.
        a, b = ('A', 'B') if seed % 2 == 0 else ('B', 'A')
        self.s.update(prior=a, alternative=b)
        if line in {'P1', 'P2'}:
            if family not in {'H', 'E', 'O', 'U'}:
                raise ValueError(family)
            self.s['hidden'] = dict(target=b if family == 'H' else a,
                delivered=family != 'E', sensor_stale=family == 'O')
            if family == 'U':
                self.s['hidden']['target'] = (a, b)[(seed // 2) % 2]
                self.s['hidden']['delivered'] = self.s['hidden']['target'] != a
            self.s['applied'] = a if family == 'O' else None
            self.s['last'] = f'Prior configuration {a} submitted. Monitor: service unavailable. Receipt and monitor validity not checked.'
        elif line == 'P3':
            if family not in {'recoverable', 'fragile_success', 'irrecoverable'}:
                raise ValueError(family)
            self.s.update(stage=1, window=2, hidden={'required_stage': 3})
            if family == 'irrecoverable':
                self.s['remaining'] = 1
            self.s['last'] = 'Job partially complete. Status pending; next observation not yet available.'
        elif line == 'P5':
            self._dag(family)
        else:
            raise ValueError(line)
        self.initial = copy.deepcopy(self.s)

    def _dag(self, family):
        if family not in {'A', 'B', 'C'}:
            raise ValueError(family)
        # Two branches and a join, plus a shared independent credential prerequisite.
        deps = {'snapshot': [], 'credentials': [], 'left': ['snapshot'],
                'right': ['snapshot', 'credentials'], 'merge': ['left', 'right'],
                'publish': ['merge', 'credentials']}
        required = dict.fromkeys(deps, 1)
        # A changes one branch; B changes common ancestor; C can be a false alarm.
        changed = 'left' if family == 'A' else 'snapshot'
        actual_change = family != 'C' or self.s['seed'] % 5 != 0
        self.s.update(deps=deps, required=required, done={}, generations=dict.fromkeys(deps, 0),
                      hidden={'changed': changed, 'actual_change': actual_change}, audited=False)
        for node in ['snapshot', 'credentials', 'left', 'right']:
            self._execute(node)
        if actual_change:
            required[changed] = 2
        self.s['last'] = (f'Authoritative requirement: {changed} revision 2 is required.' if family != 'C'
                          else 'Unverified report (reliability 0.8): snapshot revision 2 might be required. Audit available; report is not authoritative.')

    def valid(self, node):
        s = self.s
        stamp = s['done'].get(node)
        return bool(stamp and stamp['revision'] == s['required'][node]
                    and all(self.valid(d) and stamp['inputs'][d] == s['generations'][d]
                            for d in s['deps'][node]))

    def _execute(self, node):
        if not all(self.valid(d) for d in self.s['deps'][node]):
            return False
        self.s['generations'][node] += 1
        self.s['done'][node] = dict(revision=self.s['required'][node],
            inputs={d: self.s['generations'][d] for d in self.s['deps'][node]})
        return True

    def snapshot(self):
        return copy.deepcopy(dict(state=self.s, initial=self.initial))

    @classmethod
    def restore(cls, snapshot):
        obj = cls.__new__(cls)
        obj.s, obj.initial = copy.deepcopy(snapshot['state']), copy.deepcopy(snapshot['initial'])
        if obj.s['version'] != cls.VERSION:
            raise ValueError('checkpoint version')
        return obj

    def observe(self):
        s = self.s
        out = dict(observation=s['last'], remaining=s['remaining'], terminal=s['terminal'])
        if s['line'] in {'P1', 'P2'}:
            out['prior'] = s['prior']
        elif s['line'] == 'P3':
            out.update(completed_stage=s['stage'], window=s['window'])
        else:
            # Stored execution stamps are visible. Live validity/requirements are NOT.
            out.update(plan_dependencies=copy.deepcopy(s['deps']), completed=copy.deepcopy(s['done']))
            out['inherited_plan'] = ['merge','publish','verify']
        return out

    def actions(self):
        if self.s['line'] in {'P1', 'P2'}:
            return [dict(kind='receipt'), dict(kind='compatibility'), dict(kind='audit_monitor'),
                    dict(kind='apply', target='A'), dict(kind='apply', target='B'), dict(kind='verify'), dict(kind='wait')]
        if self.s['line'] == 'P3':
            return [dict(kind=k) for k in ['advance', 'wait', 'rollback', 'probe', 'verify']]
        return [dict(kind='execute_node', node=n) for n in self.s['deps']] + [dict(kind='audit'), dict(kind='verify')]

    def step(self, action):
        # Exact whitelist includes arguments: no ignored target or silently accepted extra field.
        if action not in self.actions():
            raise ValueError('action does not match v03 schema')
        s = self.s
        if s['remaining'] <= 0 or s['terminal']:
            raise RuntimeError('terminal or budget exhausted')
        s['remaining'] -= 1
        k = action['kind']; invalid = False; unnecessary = False
        if s['line'] in {'P1', 'P2'}:
            h = s['hidden']
            if k == 'receipt':
                s['last'] = 'Prior submission receipt: ' + ('delivered' if h['delivered'] else 'absent')
            elif k == 'compatibility':
                s['last'] = f"Prior {s['prior']} compatibility: " + ('compatible' if h['target'] == s['prior'] else 'incompatible')
            elif k == 'audit_monitor':
                s['last'] = 'Independent monitor: ' + ('stale; current change present' if h['sensor_stale'] else 'current; service not restored' if s['applied'] != h['target'] else 'current; change present')
                h['sensor_stale'] = False
            elif k == 'apply':
                s['applied'] = action['target']
                invalid = s['applied'] != h['target']
                s['last'] = 'Submission delivered. Monitor: ' + ('service unavailable' if invalid else 'change present')
            elif k == 'verify':
                s['success'] = s['applied'] == h['target'] and not h['sensor_stale']
                s['last'] = 'Verified.' if s['success'] else 'Verification not passed.'
            else:
                s['last'] = 'No new observation.'
        elif s['line'] == 'P3':
            fragile = s['family'] == 'fragile_success'
            if k == 'rollback':
                s['stage'] = 0; s['last'] = 'Reversible rollback completed; progress removed.'
            elif k == 'advance':
                if s['window'] > 0:
                    s['stage'] = min(3, s['stage'] + 1)
                else:
                    invalid = True
                s['last'] = 'Advance accepted.' if not invalid else 'Recovery window closed.'
            elif k == 'wait':
                if fragile and s['window'] > 0:
                    s['stage'] = 3
                s['last'] = 'Scheduled observation: stage ' + str(s['stage'])
            elif k == 'probe':
                s['last'] = 'Independent status: stage ' + str(s['stage'])
            elif k == 'verify':
                s['success'] = s['stage'] == 3
                s['last'] = 'Verified.' if s['success'] else 'Not complete.'
            s['window'] = max(0, s['window'] - 1)
        else:
            if k == 'audit':
                s['audited'] = True
                node = s['hidden']['changed']
                s['last'] = f"Authoritative audit: {node} required revision {s['required'][node]}."
            elif k == 'execute_node':
                n = action['node']; unnecessary = self.valid(n)
                invalid = not self._execute(n)
                s['last'] = f'{n}: ' + ('rejected; invalid prerequisite' if invalid else 'executed with current requirement and input versions')
            else:
                s['success'] = self.valid('publish')
                s['last'] = 'Verified.' if s['success'] else 'Verification failed: publish or dependencies invalid.'
        if s['success']:
            s['terminal'] = True
        s['history'].append(dict(action=copy.deepcopy(action), observation=s['last'],
                                 invalid=invalid, unnecessary=unnecessary))
        return self.observe()

    def score(self):
        s = self.s; hs = s['history']
        out = dict(task_success=s['success'], tool_cost=len(hs), net_utility=int(s['success'])-0.05*len(hs),
                   invalid_actions=sum(h['invalid'] for h in hs),
                   status='SUCCESS' if s['success'] else 'BUDGET_TRUNCATION' if not s['remaining'] else 'AGENT_TASK_FAIL')
        if s['line'] in {'P1','P2'}:
            changes=[h for h in hs if h['action']['kind']=='apply']
            out.update(diagnostic_tools_called=[h['action']['kind'] for h in hs if h['action']['kind'] in {'receipt','compatibility','audit_monitor'}],
                wrong_target_modifications=sum(h['invalid'] for h in changes),
                first_relevant_action_correct=(changes[0]['action']['target']==s['hidden']['target']) if changes else None,
                attribution_report_accuracy=None, fact_reception=None, belief_report_correctness=None)
        if s['line'] == 'P5':
            initial = World.restore(dict(state=self.initial, initial=self.initial))
            valid_initial = {n for n in s['deps'] if initial.valid(n)}
            touched = {h['action'].get('node') for h in hs if not h['invalid']}
            out.update(valid_work_retention=len(valid_initial-touched)/max(1, len(valid_initial)),
                       unnecessary_reexecution=sum(h['unnecessary'] for h in hs),
                       obsolete_action_attempts=sum(h['invalid'] for h in hs),
                       obsolete_action_execution=0,  # Invalid prerequisites are rejected before effects.
                       plan_consistency={n: self.valid(n) for n in s['done']})
        return out


def shortest_success(world, max_depth=None):
    """Privileged exhaustive planner for fixture GT, never an ordinary agent."""
    limit = min(world.s['remaining'], max_depth if max_depth is not None else world.s['remaining'])
    queue = deque([(world.snapshot(), [])]); seen = set(); expanded = 0
    while queue:
        snap, path = queue.popleft(); w = World.restore(snap); expanded += 1
        if w.s['success']:
            return dict(actions=path, expanded=expanded, feasible=True)
        if len(path) >= limit:
            continue
        key_state = copy.deepcopy(w.s)
        key_state.pop('history'); key_state.pop('last')
        # DAG generation numbers need canonicalization to avoid unbounded redo permutations.
        if w.s['line'] == 'P5':
            key_state = dict(valid={n:w.valid(n) for n in w.s['deps']}, remaining=w.s['remaining'])
        key = digest(key_state)
        if key in seen:
            continue
        seen.add(key)
        for a in w.actions():
            child = World.restore(snap); child.step(a)
            queue.append((child.snapshot(), path+[a]))
    return dict(actions=None, expanded=expanded, feasible=False)
