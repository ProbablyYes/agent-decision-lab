"""Exact finite-horizon belief DP. Policies receive distributions, never realized GT.

State=(x,y,calibrated,first_probe,progress,time). Deterministic conditional
observations are an explicit special case of observation probabilities 0/1.
"""
from fractions import Fraction as F
from functools import lru_cache
from math import log2
import copy

COST = F(1, 20)
ACTIONS = {'A': ('calibrate', 'measure', 'guess0', 'guess1'),
           'B': ('probe1', 'probe2', 'guess0', 'guess1'),
           'C': ('prepare', 'measure', 'dual', 'guess0', 'guess1'),
           'D': ('wait', 'measure', 'guess0', 'guess1')}


def prior(family):
    states = [(x, y, 0, 0, 0, 0) for x in (0, 1) for y in ((0, 1) if family == 'B' else (0,))]
    return tuple((s, F(1, len(states))) for s in states)


def target(family, state):
    return state[0] ^ state[1] if family == 'B' else state[0]


def transition(family, state, action):
    x, y, cal, first, progress, t = state
    if action not in ACTIONS[family]:
        raise ValueError('illegal family action')
    if action.startswith('guess'):
        ok = int(action[-1]) == target(family, state)
        ok &= family != 'C' or progress == 1
        ok &= family != 'D' or t < 2
        return [(F(1), state, 'terminal', F(int(ok))-COST, True)]
    signal = 'none'
    if action in {'calibrate', 'prepare'}:
        cal = 1
        if action == 'prepare':
            progress = 1
    elif action == 'measure':
        if family == 'A' and cal or family == 'C':
            signal = str(x)
        # D immediate observation is stale/inconclusive; the scheduled wait reveals it.
    elif action == 'probe1':
        first = 1; signal = str(x)
    elif action == 'probe2' and first:
        signal = str(y)
    elif action == 'dual':
        signal = str(x); progress = 1
    elif action == 'wait' and t == 0:
        signal = str(x)
    ns = (x, y, cal, first, progress, t+1)
    observation = (signal, cal, first, progress, t+1)
    return [(F(1), ns, observation, -COST, False)]


def branches(family, belief, action):
    groups = {}; reward = F(0); terminal = action.startswith('guess')
    for state, mass in belief:
        for probability, ns, obs, r, done in transition(family, state, action):
            weight = mass*probability; reward += weight*r
            groups.setdefault(obs, {})[ns] = groups.setdefault(obs, {}).get(ns, F(0)) + weight
    result = []
    for obs, states in groups.items():
        probability = sum(states.values(), F(0))
        result.append((probability, tuple(sorted((s, p/probability) for s,p in states.items())), obs))
    return reward, terminal, result


@lru_cache(None)
def solve(family, belief, horizon, leaf_guess=False):
    if horizon == 0:
        value = max(branches(family, belief, a)[0] for a in ('guess0', 'guess1')) if leaf_guess else F(0)
        return value, None
    scored = []
    for action in ACTIONS[family]:
        r, terminal, bs = branches(family, belief, action)
        q = r if terminal else r + sum(p*solve(family,b,horizon-1,leaf_guess)[0] for p,b,_ in bs)
        scored.append((q, action))
    best = max(q for q,_ in scored)
    # Ties prefer an immediate terminal choice, then the declared public order.
    choices = [a for q,a in scored if q == best]
    action = next((a for a in ('guess0', 'guess1') if a in choices), choices[0])
    return best, action


def entropy(family, belief):
    p = sum(mass for state,mass in belief if target(family,state) == 1)
    return sum(-float(q)*log2(float(q)) for q in (p, 1-p) if q)


def select(family, belief, remaining, policy):
    if policy == 'exact':
        return solve(family,belief,remaining)[1]
    if policy == 'lookahead2':
        # Stronger truncation heuristic: best immediate terminal utility at leaves.
        return solve(family,belief,min(2,remaining),remaining > 2)[1]
    if policy == 'immediate':
        return max(ACTIONS[family], key=lambda a: branches(family,belief,a)[0])
    if policy == 'information_gain':
        scored = []
        for a in ACTIONS[family]:
            if a.startswith('guess'):
                continue
            _,_,bs = branches(family,belief,a)
            gain = entropy(family,belief)-sum(float(p)*entropy(family,b) for p,b,_ in bs)
            progress = sum(float(p)*sum(float(q)*s[4] for s,q in b) for p,b,_ in bs)
            scored.append((gain, progress, a))
        gain, _, a = max(scored)
        return a if gain > 1e-12 else max(('guess0','guess1'),key=lambda a:branches(family,belief,a)[0])
    raise ValueError(policy)


def policy_value(family, policy, horizon=4, belief=None):
    belief = prior(family) if belief is None else belief
    if not horizon:
        return F(0)
    a = select(family,belief,horizon,policy)
    r, terminal, bs = branches(family,belief,a)
    return r if terminal else r + sum(p*policy_value(family,policy,horizon-1,b) for p,b,_ in bs)


def report():
    result = {}
    for family in ACTIONS:
        exact = policy_value(family,'exact')
        result[family] = {'hidden_distribution': [[list(s), str(p)] for s,p in prior(family)],
            'horizon':4, 'action_cost':str(COST), 'observation_probabilities':'deterministic conditional 0/1',
            'terminal_utility':'1 if correct and preconditions/window satisfied, else 0; each action costs 1/20',
            'policies':{p:{'expected_net_return':str(policy_value(family,p)),
                           'regret':str(exact-policy_value(family,p)),
                           **policy_stats(family,p,4,prior(family)),
                           'first_action':select(family,prior(family),4,p)}
                        for p in ('immediate','information_gain','lookahead2','exact')}}
    result['complexity'] = dict(solve_cache=solve.cache_info()._asdict(),
        bound='finite tree O(|A|^H * |O|^H * |S|), memoized by normalized rational belief and horizon')
    return result


def policy_stats(family, policy, horizon, belief):
    if not horizon:
        return {'expected_success': '0', 'expected_actions':'0'}
    a = select(family,belief,horizon,policy)
    r, terminal, bs = branches(family,belief,a)
    if terminal:
        return {'expected_success':str(r+COST),'expected_actions':'1'}
    children = [(p,policy_stats(family,policy,horizon-1,b)) for p,b,_ in bs]
    return {'expected_success':str(sum(p*F(c['expected_success']) for p,c in children)),
            'expected_actions':str(1+sum(p*F(c['expected_actions']) for p,c in children))}


class BeliefSession:
    """Realized finite simulator with public posterior and evaluator-only state."""
    def __init__(self,family,seed=0,horizon=4):
        self.family=family; self.belief=prior(family)
        self.hidden=self.belief[seed % len(self.belief)][0]
        self.remaining=horizon; self.history=[]; self.terminal=False; self.utility=F(0)

    def observe(self):
        return {'belief':[[list(s),str(p)] for s,p in self.belief],
                'remaining':self.remaining,'terminal':self.terminal,'history':copy.deepcopy(self.history)}

    def snapshot(self):
        return {'version':'v03-pomdp-1','family':self.family,'public':self.observe(),
                'evaluator_hidden':list(self.hidden),'utility':str(self.utility)}

    @classmethod
    def restore(cls,cp):
        if cp['version']!='v03-pomdp-1':
            raise ValueError('checkpoint version')
        obj=cls(cp['family']); obj.belief=tuple((tuple(s),F(p)) for s,p in cp['public']['belief'])
        obj.hidden=tuple(cp['evaluator_hidden']); obj.remaining=cp['public']['remaining']
        obj.history=copy.deepcopy(cp['public']['history']); obj.terminal=cp['public']['terminal']; obj.utility=F(cp['utility'])
        return obj

    def step(self,action):
        if self.terminal or self.remaining<=0:
            raise RuntimeError('terminal or horizon exhausted')
        _,ns,obs,reward,terminal=transition(self.family,self.hidden,action)[0]
        _,_,bs=branches(self.family,self.belief,action)
        self.belief=next(b for _,b,o in bs if o==obs)
        self.hidden=ns; self.remaining-=1; self.terminal=terminal; self.utility+=reward
        self.history.append({'action':action,'observation':list(obs) if isinstance(obs,tuple) else obs,'reward':str(reward)})
        return self.observe()
