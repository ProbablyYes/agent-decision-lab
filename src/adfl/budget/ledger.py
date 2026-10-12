"""SQLite is the source of truth for approvals, spend and recoverable sessions."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from adfl.budget.guard import BudgetStop


class Ledger:
    def __init__(self, path, *, create=False):
        self.path = Path(path).resolve()
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive filesystem creation prevents a second initializer resetting a live ledger.
            with self.path.open("xb"):
                pass
        elif not self.path.is_file():
            raise BudgetStop("ledger missing: stop, do not reset spending to zero")
        with self.transaction() as db:
            if create:
                db.executescript("""
                CREATE TABLE account(id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER NOT NULL);
                INSERT INTO account VALUES(1,8000000);
                CREATE TABLE runs(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, approval TEXT,
                  reviewed TEXT, status TEXT NOT NULL, session TEXT NOT NULL,
                  spend_cap INTEGER NOT NULL);
                CREATE TABLE requests(id TEXT PRIMARY KEY, run TEXT NOT NULL, step INTEGER NOT NULL,
                  reserved INTEGER NOT NULL, calculated INTEGER, billed INTEGER, status TEXT NOT NULL,
                  request TEXT NOT NULL, response TEXT, usage TEXT, evidence TEXT, UNIQUE(run,step));
                CREATE TABLE audit(id INTEGER PRIMARY KEY, time TEXT DEFAULT CURRENT_TIMESTAMP,
                  event TEXT NOT NULL, details TEXT NOT NULL);
                """)
                self.audit(db, "ledger_initialized", {"prior_real_spend_cny": 0, "gate": 1})
            else:
                if db.execute("SELECT cap FROM account WHERE id=1").fetchone() is None:
                    raise BudgetStop("invalid ledger")
                if "spend_cap" not in {r[1] for r in db.execute("PRAGMA table_info(runs)")}:
                    raise BudgetStop("old ledger requires reviewed migration; do not recreate or reset spending")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            if db.in_transaction:
                db.commit()
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def audit(db, event, details):
        db.execute("INSERT INTO audit(event,details) VALUES(?,?)", (event, json.dumps(details, ensure_ascii=False)))

    @staticmethod
    def exposure(db):
        return db.execute("SELECT COALESCE(SUM(CASE WHEN billed IS NULL THEN reserved ELSE billed END),0) FROM requests").fetchone()[0]

    def register(self, run_id, fingerprint, session, *, spend_cap=8000000):
        if type(spend_cap) is not int or not 0 < spend_cap <= 8000000:
            raise BudgetStop("invalid independent trajectory cap")
        with self.transaction() as db:
            db.execute("INSERT INTO runs(id,fingerprint,status,session,spend_cap) VALUES(?,?,?,?,?)", (run_id, fingerprint, "ready", json.dumps(session), spend_cap))
            self.audit(db, "run_registered", {"run": run_id, "spend_cap_micro_cny": spend_cap})

    def approve(self, run_id, fingerprint, evidence, *, ready=False, predecessor=None, retain_unknown_bills=False):
        if not ready or not evidence.strip():
            raise BudgetStop("model/price/FX/account confirmation and explicit human evidence required")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["fingerprint"] != fingerprint or row["status"] != "ready":
                raise BudgetStop("approval does not match a frozen ready run")
            if retain_unknown_bills and run_id not in {"g1-01b", "g1-02", "g1-03"}:
                raise BudgetStop("continuation authorization limited to three named trajectories")
            pending_sql = "SELECT 1 FROM runs WHERE approval IS NOT NULL AND reviewed IS NULL AND id<>?"
            if retain_unknown_bills:
                pending_sql += " AND status NOT IN ('completed','failed')"
            if db.execute(pending_sql, (run_id,)).fetchone():
                raise BudgetStop("previous approved trajectory requires review")
            if predecessor:
                prev = db.execute("SELECT reviewed,status FROM runs WHERE id=?", (predecessor,)).fetchone()
                if not prev or not (prev[0] or (retain_unknown_bills and prev[1] in {'completed','failed'})):
                    raise BudgetStop("predecessor review required")
            db.execute("UPDATE runs SET approval=? WHERE id=?", (evidence, run_id))
            self.audit(db, "human_approval", {"run": run_id, "fingerprint": fingerprint, "evidence": evidence, "unknown_bills_remain_reserved": retain_unknown_bills})

    def reserve(self, run_id, fingerprint, step, amount, payload):
        if type(amount) is not int or amount <= 0:
            raise BudgetStop("reservation must be positive integer micro-CNY")
        req_id = run_id + ":" + str(step)
        with self.transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or row["fingerprint"] != fingerprint or not row["approval"] or row["status"] not in {"ready", "running"}:
                raise BudgetStop("frozen run not approved")
            session = json.loads(row["session"])
            if step != session["decisions"] + 1 or step > 8:
                raise BudgetStop("decision sequence/limit violated")
            if db.execute("SELECT 1 FROM requests WHERE status IN ('reserved','received','ambiguous','billing_mismatch')").fetchone():
                raise BudgetStop("outstanding request: recover/reconcile; never resend")
            cap = min(db.execute("SELECT cap FROM account WHERE id=1").fetchone()[0], 10000000, 90000000, 100000000)
            if self.exposure(db) + amount > cap:
                raise BudgetStop("cumulative budget exceeded")
            run_exposure = db.execute("SELECT COALESCE(SUM(CASE WHEN billed IS NULL THEN reserved ELSE billed END),0) FROM requests WHERE run=?", (run_id,)).fetchone()[0]
            if run_exposure + amount > row["spend_cap"]:
                raise BudgetStop("independent trajectory budget exceeded")
            db.execute("INSERT INTO requests(id,run,step,reserved,status,request) VALUES(?,?,?,?,?,?)",
                       (req_id, run_id, step, amount, "reserved", json.dumps(payload)))
            db.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
            self.audit(db, "request_reserved", {"request": req_id, "micro_cny": amount})
        return req_id

    def receive(self, request_id, response, usage=None, calculated=None, *, valid=True, allow_estimate=False):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row or row["status"] != "reserved":
                raise BudgetStop("response not matched to reservation")
            safe = valid and ((calculated is not None and calculated <= row["reserved"]) or
                              (allow_estimate and row["run"] in {"g1-01", "g1-01b", "g1-02", "g1-03"} and calculated is None))
            db.execute("UPDATE requests SET response=?,usage=?,calculated=?,status=? WHERE id=?",
                (json.dumps(response), json.dumps(usage), calculated, "received" if safe else "ambiguous", request_id))
            self.audit(db, "response_saved", {"request": request_id, "usage_valid": safe, "estimate_authorized": allow_estimate})
            if not safe:
                run = db.execute("SELECT session FROM runs WHERE id=?", (row["run"],)).fetchone()
                session = json.loads(run[0])
                session["error"] = response.get("cost_error") or response.get("transport_error") or "unknown or excessive cost; reservation retained"
                db.execute("UPDATE runs SET status='paused_unknown_cost',session=? WHERE id=?", (json.dumps(session), row["run"]))

    def apply(self, request_id, session, trajectory, *, terminal=False, error=None):
        # Environment state, tool history, decision count and request consumption commit together.
        with self.transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row or row["status"] != "received":
                raise BudgetStop("no durable response to apply")
            db.execute("UPDATE requests SET status='applied' WHERE id=?", (request_id,))
            db.execute("UPDATE runs SET session=?,status=? WHERE id=?",
                       (json.dumps(session), "failed" if error else "completed" if terminal else "running", row["run"]))
            self.audit(db, "decision_applied", {"run": row["run"], "request": request_id, "trajectory": trajectory, "error": error})

    def reconcile(self, request_id, billed, usage, evidence, *, process_stopped=False):
        if type(billed) is not int or billed < 0 or not evidence.strip():
            raise BudgetStop("actual bill and evidence required; unknown cannot be zero")
        mismatch = False
        with self.transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row or row["billed"] is not None or (row["status"] == "reserved" and not process_stopped):
                raise BudgetStop("unknown/in-flight/already reconciled request")
            actual_usage = json.dumps(usage, sort_keys=True)
            prior_usage = json.dumps(json.loads(row["usage"]) if row["usage"] else None, sort_keys=True)
            mismatch = row["calculated"] is not None and (actual_usage != prior_usage or abs(billed - row["calculated"]) > max(2, row["calculated"] // 100))
            if billed > row["reserved"] or mismatch:
                # Retain the larger liability even on accounting anomalies.
                db.execute("UPDATE requests SET reserved=?,billed=?,evidence=?,status='billing_mismatch' WHERE id=?", (max(billed,row["reserved"]),billed,evidence,request_id))
                db.execute("UPDATE runs SET status='paused_unknown_cost' WHERE id=?", (row["run"],))
            else:
                db.execute("UPDATE requests SET billed=?,evidence=? WHERE id=?", (billed, evidence, request_id))
            self.audit(db, "bill_reconciled", {"request": request_id, "billed_micro_cny": billed, "evidence": evidence})
        if mismatch:
            raise BudgetStop("bill/usage mismatch persisted; manual investigation required")

    def close_uncertain(self, run_id, evidence, *, process_stopped=False):
        """Manual termination after a crashed process and itemized bill review. Never resend."""
        if not process_stopped or not evidence.strip():
            raise BudgetStop("operator must confirm worker stopped and supply closing evidence")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or row["status"] in {"completed", "failed"}:
                raise BudgetStop("not an uncertain run")
            reqs = db.execute("SELECT * FROM requests WHERE run=?", (run_id,)).fetchall()
            if not reqs or any(r["billed"] is None for r in reqs):
                raise BudgetStop("unknown bills remain reserved; cannot close")
            session = json.loads(row["session"])
            session["error"] = "human-closed uncertain request; " + evidence
            db.execute("UPDATE runs SET status='failed',session=? WHERE id=?", (json.dumps(session),run_id))
            db.execute("UPDATE requests SET status='aborted' WHERE run=? AND status<>'applied'", (run_id,))
            self.audit(db, "uncertain_run_closed", {"run":run_id,"evidence":evidence})

    def review(self, run_id, evidence):
        with self.transaction() as db:
            row = db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if not evidence.strip() or not row or row[0] not in {"completed", "failed"}:
                raise BudgetStop("terminal trajectory and human review required")
            if db.execute("SELECT 1 FROM requests WHERE run=? AND billed IS NULL", (run_id,)).fetchone():
                raise BudgetStop("all request bills must be reconciled before review")
            db.execute("UPDATE runs SET reviewed=? WHERE id=?", (evidence, run_id))
            self.audit(db, "trajectory_reviewed", {"run": run_id, "evidence": evidence})

    def snapshot(self, run_id=None):
        with self.transaction() as db:
            runs = [dict(r) for r in db.execute("SELECT * FROM runs" + (" WHERE id=?" if run_id else ""), (run_id,) if run_id else ())]
            requests = [dict(r) for r in db.execute("SELECT * FROM requests" + (" WHERE run=?" if run_id else "") + " ORDER BY rowid", (run_id,) if run_id else ())]
            audit = [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id")]
            return {"exposure_micro_cny": self.exposure(db), "actual_verified_micro_cny": sum(r[0] for r in db.execute("SELECT billed FROM requests WHERE billed IS NOT NULL")),
                    "unreconciled_requests": db.execute("SELECT COUNT(*) FROM requests WHERE billed IS NULL").fetchone()[0],
                    "runs": runs, "requests": requests, "audit": audit}
