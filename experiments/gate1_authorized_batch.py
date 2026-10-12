"""Execute only the three explicitly authorized Gate 1 trajectories, serially.

Usage: python experiments/gate1_authorized_batch.py g1-01b|g1-02|g1-03
Unknown bills remain reserved. This is an execution launcher, not a research policy.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from adfl.budget.guard import BudgetStop
from adfl.budget.ledger import Ledger
from adfl.gate1 import ROOT, LEDGER_PATH, Gate1Engine, export, fingerprint, initial_session

ALLOWED = {'g1-01b': ('p1', 'attribution:H'), 'g1-02': ('p1', 'attribution:E'), 'g1-03': ('p2', 'plan:H')}
EVIDENCE = ('User explicitly authorized only g1-01b, g1-02, g1-03 after minimal stop/tool_calls compatibility fix; '
            'continue only after complete real tool loop and normal ledger; no retries/model changes; '
            'unknown bills retain reservation; Gate 1 <= CNY10, stricter batch <= CNY8 and each run <= CNY1.')


def check_finished(ledger, rid, require_loop=False):
    snap = ledger.snapshot(rid)
    if not snap['runs'] or snap['runs'][0]['status'] not in {'completed', 'failed'}:
        raise BudgetStop('predecessor not terminal')
    session = json.loads(snap['runs'][0]['session'])
    if session['error'] not in {None, 'decision/action budget exhausted'}:
        raise BudgetStop('new interface/environment error; no subsequent trajectory')
    if any(r['status'] != 'applied' for r in snap['requests']):
        raise BudgetStop('unconsumed/ambiguous predecessor request')
    if require_loop:
        reqs = snap['requests']
        if len(reqs) < 2 or session['decisions'] < 2:
            raise BudgetStop('no full real tool round trip')
        messages = json.loads(reqs[1]['request'])['messages']
        if messages[-1]['role'] != 'tool' or messages[-1]['tool_call_id'] != messages[-2]['tool_calls'][0]['id']:
            raise BudgetStop('missing matching tool result in next real request')
    with ledger.transaction() as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise BudgetStop('ledger integrity failed')
        if ledger.exposure(db) > 8000000:
            raise BudgetStop('ledger budget exceeded')


def main(rid):
    if rid not in ALLOWED:
        raise BudgetStop('outside authorized scope')
    config = json.loads((ROOT/'configs/gate1.json').read_text(encoding='utf-8'))
    ledger = Ledger(LEDGER_PATH)
    if rid != 'g1-01b':
        check_finished(ledger, 'g1-01b', require_loop=True)
    if rid == 'g1-03':
        check_finished(ledger, 'g1-02')
    destination = ROOT/'results/gate1'/rid
    if destination.exists():
        raise BudgetStop('output already exists; no overwrite or automatic rerun')
    old = ledger.snapshot(rid)
    if old['requests'] or (old['runs'] and (old['runs'][0]['approval'] or old['runs'][0]['status'] != 'ready')):
        raise BudgetStop('run previously started/approved; no rerun')
    backup = ROOT/'.state/backups'/('gate1-before-'+rid+'.sqlite3')
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        raise BudgetStop('backup exists; investigate instead of repeating launcher')
    with sqlite3.connect(LEDGER_PATH) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    if rid == 'g1-01b':
        original = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (ROOT/'results/gate1/g1-01').rglob('*') if p.is_file()}
        (ROOT/'.state/g1-01-original-hashes.json').write_text(json.dumps(original, indent=2), encoding='utf-8')
    fp = fingerprint(config)
    if old['runs']:
        # Only untouched registrations are rebound; requests/history are never rewritten.
        with ledger.transaction() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?', (rid,)).fetchone()
            if row['approval'] or row['status'] != 'ready' or db.execute('SELECT 1 FROM requests WHERE run=?',(rid,)).fetchone():
                raise BudgetStop('run changed during preparation')
            db.execute('UPDATE runs SET fingerprint=?,spend_cap=1000000 WHERE id=?', (fp,rid))
            ledger.audit(db,'unstarted_run_rebound',{'run':rid,'old_fingerprint':row['fingerprint'],'fingerprint':fp,'evidence':EVIDENCE})
    else:
        line, task = ALLOWED[rid]
        ledger.register(rid, fp, initial_session(task,line), spend_cap=1000000)
    predecessor = {'g1-02':'g1-01b','g1-03':'g1-02'}.get(rid)
    ledger.approve(rid,fp,EVIDENCE,ready=True,predecessor=predecessor,retain_unknown_bills=True)
    try:
        Gate1Engine(ledger,config).run(rid)
    finally:
        export(ledger,config,rid,destination)
    print(json.dumps(json.loads((destination/'metrics.json').read_text(encoding='utf-8')),ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
