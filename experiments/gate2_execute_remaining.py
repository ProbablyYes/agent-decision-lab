"""Continue the frozen seven-branch batch once; stop on any new interface error."""
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
from gate2_billing import check
from adfl.budget.guard import BudgetStop
from adfl.budget.ledger import Ledger
from adfl.gate1 import LEDGER_PATH


def main():
    root=Path('results/gate2'); c=json.loads((root/'preregistration.json').read_text(encoding='utf-8'))
    ledger=Ledger(LEDGER_PATH); previous=json.loads((root/'billing/before.json').read_text())
    for i,(rid,line,arm) in enumerate(c['run_order']):
        snap=ledger.snapshot(rid)
        if i==0:
            if snap['runs'][0]['status'] not in {'completed','failed'}:
                raise BudgetStop('first branch not finished; do not launch duplicate worker')
        else:
            if snap['requests'] or snap['runs'][0]['status']!='ready':
                raise BudgetStop('branch already started; no automatic rerun')
            print('RUN '+rid,flush=True)
            subprocess.run([sys.executable,'-m','adfl.gate2','run','--run-id',rid],check=True)
            snap=ledger.snapshot(rid)
        session=json.loads(snap['runs'][0]['session'])
        if snap['runs'][0]['status'] not in {'completed','failed'} or session['error'] not in {None,'decision/action budget exhausted'}:
            raise BudgetStop('new interface/harness error; stop subsequent branches')
        check('after-'+rid)
        current=json.loads((root/'billing'/('after-'+rid+'.json')).read_text())
        if current.get('status')!=200 or current.get('account',{}).get('currency')!='USD' or not current['account'].get('is_active'):
            raise BudgetStop('account check failed; no subsequent branch')
        if previous.get('status')!=200:
            raise BudgetStop('missing previous balance evidence')
        delta=Decimal(str(current['account']['used']))-Decimal(str(previous['account']['used']))
        retained=Decimal(sum(r['reserved'] for r in snap['requests']))/1000000
        if delta<0 or delta*Decimal(c['pricing']['cny_per_usd'])>retained:
            raise BudgetStop('account-level spending change exceeds conservative branch reservation; stop')
        print('END '+rid+' account_used_delta_usd='+str(delta)+' retained_cny='+str(retained),flush=True)
        previous=current
    print('Seven registered branches ended; paused. No additional experiments.',flush=True)


if __name__=='__main__': main()
