"""Versioned Gate 2 fixtures. Gate 1 CDW semantics remain unchanged."""
import copy
from adfl.world.cdw import CDW


class PilotWorld(CDW):
    def reset(self, task_id, seed=0):
        family, truth = task_id.split(':')
        if family not in {'ambiguous', 'dependency', 'complementary'} or truth not in {'H','E'}:
            raise ValueError('unknown pilot fixture')
        super().reset('attribution:'+truth, seed)
        self.s.update(task_id=task_id, family=family, prefix_actions=0, prepared_once=False,
                      staged=None, tested=None, probes=[], delivered=False, changed=False)
        if family == 'complementary':
            first_bit=self.rng.randrange(2)
            self.s['probe_bits']=[first_bit,first_bit ^ int(truth=='H')]
        if family == 'dependency':
            self.s['world_state']['target'] = 'A'
            self.step({'kind':'prepare'})
            self.step({'kind':'calibrate'})
            self.step({'kind':'inspect','target':'A'})
            self.s['world_state']['target'] = 'B'  # exogenous requirement update, not an agent action
            self.s['changed'] = True
            self.s['plan_DAG'] = {'snapshot':[], 'credentials':[], 'stage:A':['snapshot','credentials'],
                'apply:A':['stage:A'], 'smoke:A':['apply:A'], 'verify:A':['smoke:A']}
            self.s['invalid_nodes'] = ['stage:A','apply:A','smoke:A','verify:A']
            self.last = 'Requirement update: configuration B is now required. Shared snapshot and credentials remain valid.'
        else:
            self.step({'kind':'apply_change','target':'A'})
        self.s['prefix_actions'] = len(self.s['history'])
        return self.get_observation()

    def step(self, action):
        if action.get('kind') == 'combo':
            return super().step(action)
        if self.s['remaining_budget'] <= 0:
            raise RuntimeError('action budget exhausted')
        kind, target = action.get('kind'), action.get('target')
        if kind not in {'inspect','diagnose','prepare','calibrate','apply_change','verify','undo','wait'}:
            raise ValueError('unknown action')
        if kind == 'apply_change' and target not in {'A','B'}:
            raise ValueError('target required')
        self.s['remaining_budget'] -= 1
        w = self.s['world_state']; before = copy.deepcopy(w)
        invalid = False; node = None; family = self.s['family']
        if family == 'dependency':
            if kind == 'prepare':
                node='snapshot'; w['prepared']=True; self.last='Shared snapshot available; any existing snapshot is preserved.'
            elif kind == 'calibrate':
                node='credentials'; w['calibrated']=True; self.last='Shared credentials validated; existing credentials remain valid.'
            elif kind == 'inspect':
                node='stage:'+str(target)
                if not w['prepared'] or not w['calibrated'] or target not in {'A','B'}:
                    invalid=True; self.last='Staging rejected: snapshot, credentials and target required.'
                else:
                    self.s['staged']=target; self.last=f'Configuration {target} staged and inspected.'
            elif kind == 'apply_change':
                node='apply:'+target
                if self.s['staged'] != target or target != w['target']:
                    invalid=True; self.last='Change rejected: staging or current requirement mismatch.'
                else:
                    w['applied']=True; self.last='Change applied.'
            elif kind == 'diagnose':
                node='smoke:'+str(target)
                if w['applied'] and target == w['target']:
                    self.s['tested']=target; self.last='Smoke test passed; test result registered for final verification.'
                else:
                    invalid=True; self.last='Smoke test failed: current required configuration not applied.'
            elif kind == 'verify':
                node='verify:'+str(w['target'])
                w['verified']=bool(w['applied'] and self.s['tested']==w['target'])
                self.last='Service restored and verified.' if w['verified'] else 'Verification failed: applied change and smoke test required.'
            elif kind == 'undo':
                w['applied']=w['verified']=False; self.s['tested']=None; self.last='Change undone; shared prerequisites retained.'
            else:
                self.last='No new evidence.'
        elif kind == 'apply_change':
            # E's first command is dropped; later submissions can take effect.
            first = not self.s['history']
            dropped = first and (self.s['root_cause']=='E' or family=='complementary')
            self.s['delivered'] = not dropped
            if target == w['target'] and not dropped:
                w['applied']=True; self.s['execution_fault']=False; self.last='Change applied.'
            else:
                invalid=True; self.last='Service unavailable; attempted change did not restore service.'
        elif kind == 'diagnose':
            if family == 'complementary' and not w['calibrated']:
                self.last='Uncalibrated instrument: inconclusive.'
            elif family == 'complementary' and target in {'A','B'}:
                self.last=f'Probe {target} bit: {self.s["probe_bits"][0 if target=="A" else 1]}. Use both bits: equal selects A, different selects B.'
                self.s['probes'].append(target)
            elif target == 'A':
                self.last='Command receipt: delivered.' if self.s['delivered'] else 'Command receipt: absent.'
                self.s['probes'].append('receipt')
            elif target == 'B':
                self.last='Compatibility test: configuration A compatible.' if w['target']=='A' else 'Compatibility test: configuration A incompatible.'
                self.s['probes'].append('compatibility')
            else:
                self.last='Choose diagnose A for delivery receipt or diagnose B for compatibility test.'
        elif kind == 'inspect':
            self.last='Service unavailable.' if not w['applied'] else 'Change present; verification required.'
        elif kind == 'prepare':
            w['prepared']=True; self.last='Workspace prepared.'
        elif kind == 'calibrate':
            w['calibrated']=True; self.last='Instrument calibrated; no root cause disclosed.'
        elif kind == 'verify':
            w['verified']=w['applied']; self.last='Service restored and verified.' if w['verified'] else 'Service unavailable.'
        elif kind == 'undo':
            w['applied']=w['verified']=False; self.last='Change undone.'
        else:
            self.last='No new evidence.'
        self.s['invalid_actions'] += int(invalid)
        if kind in {'inspect','diagnose'} and any(h['action']==action for h in self.s['history']):
            self.s['redundant_probes'] += 1
        self.s['history'].append({'action':copy.deepcopy(action),'before':before,'after':copy.deepcopy(w),'invalid':invalid,'node':node})
        return self.get_observation()

    def score(self):
        result = super().score()
        suffix=self.s['history'][self.s['prefix_actions']:]
        result.update(tool_calls=len(suffix), invalid_actions=sum(h['invalid'] for h in suffix))
        if self.s['family']=='dependency':
            shared={'snapshot','credentials'}
            redone={h['node'] for h in suffix} & shared
            stale=sum(h['node'] in self.s['invalid_nodes'] for h in suffix)
            result.update(invalid_action_rate=sum(h['invalid'] for h in suffix if h['action']['kind']=='apply_change') / max(1,sum(h['action']['kind']=='apply_change' for h in suffix)),
                          valid_node_retention=len(shared-redone)/len(shared),repair_cost=len(suffix),
                          completion=result['success'], stale_node_executions=stale, shared_node_reexecutions=len(redone))
        return result
