"""Gate 1 preparation and single-trajectory runner. No implicit batch execution."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from adfl.agents.tools import TOOLS, TOOL_PROMPT, PROMPT_VERSION, decode_tool
from adfl.agents.transport import OFoxTransport
from adfl.budget.guard import BudgetStop
from adfl.budget.ledger import Ledger
from adfl.budget.pricing import RateCard, usage_from, micro_cny
from adfl.world import CDW

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / ".state" / "gate1.sqlite3"
RUNS = [("g1-01", "p1", "attribution:H"), ("g1-02", "p1", "attribution:E"), ("g1-03", "p2", "plan:H")]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fingerprint(config):
    code = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "src" / "adfl").rglob("*.py"))}
    return digest({"config": config, "prompt": TOOL_PROMPT, "tools": TOOLS, "code": code})


def validate(config):
    if config.get("base_url") != "https://api.ofox.ai/v1" or config.get("provider") != "ofox":
        raise ValueError("unexpected experiment provider")
    expected = {"temperature": 0, "max_tokens": 512, "max_decisions": 8, "primitive_budget": 12,
                "seed": 0, "automatic_retries": 0, "concurrency": 1, "prompt_version": PROMPT_VERSION}
    if any(config.get(k) != v for k, v in expected.items()) or config.get("tune_on_test") is not False:
        raise ValueError("frozen Gate 1 limits changed")
    if config.get("input_token_bound") != 8192 or config.get("stage_cap_cny") != 10 or config.get("batch_cap_cny") != 8:
        raise ValueError("reviewed budget envelope changed")
    if config.get("tools_hash") != digest(TOOLS) or config.get("prompt_hash") != digest(TOOL_PROMPT):
        raise ValueError("tool/prompt hash mismatch")
    if not config.get("model_id") or config["model_id"] == "unselected":
        raise ValueError("model selection required")
    snapshot_path = ROOT / config["catalog_path"]
    raw = snapshot_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["catalog_sha256"]:
        raise ValueError("pricing catalog changed")
    model = next((m for m in json.loads(raw)["data"] if m["id"] == config["model_id"]), None)
    if not model or not {"temperature", "max_tokens", "tools", "tool_choice"}.issubset(model.get("supported_parameters", [])):
        raise ValueError("model parameters not advertised")
    if config["model_revision"] != model.get("canonical_slug"):
        raise ValueError("model catalog revision mismatch")
    rates = config["pricing"]
    for key, field in (("input", "prompt"), ("output", "completion"), ("cache_read", "input_cache_read"), ("cache_write", "input_cache_write")):
        from adfl.budget.pricing import decimal
        value = model["pricing"].get(field)
        if value is None or decimal(rates.get(key)) != decimal(value) * 1000000:
            raise ValueError("rate card differs from provider catalog")
    return config


def readiness(config):
    validate(config)
    fields = ("model_confirmed", "account_currency_confirmed", "account_rates_confirmed", "fx_confirmed", "usage_cache_semantics_confirmed")
    missing = [k for k in fields if config.get(k) is not True]
    return {"ready_for_approval": not missing, "blockers": missing, "fingerprint": fingerprint(config),
            "real_calls": 0, "estimated_three_envelope_cny": RateCard(config["pricing"]).reserve(8192,512)*24/1e6,
            "estimated_five_envelope_cny": RateCard(config["pricing"]).reserve(8192,512)*40/1e6}


def initial_session(task, line):
    w = CDW(); obs = w.reset(task, 0)
    return {"task_id": task, "line": line, "source": "SIM", "split": "pilot", "condition": "natural_continue",
            "seed": 0, "decisions": 0, "checkpoint_hash": w.checkpoint_hash(), "initial": w.snapshot(),
            "environment": w.snapshot(), "messages": [{"role": "system", "content": TOOL_PROMPT},
            {"role": "user", "content": json.dumps(obs)}], "error": None}


class Gate1Engine:
    def __init__(self, ledger, config, transport=None):
        self.ledger, self.config = ledger, validate(config)
        self.fp = fingerprint(config)
        self.rates = RateCard(config["pricing"])
        self.transport = transport or OFoxTransport(config["base_url"])

    def run(self, run_id):
        if not readiness(self.config)["ready_for_approval"]:
            raise BudgetStop("model/account pricing/FX/cache semantics not confirmed")
        while True:
            snap = self.ledger.snapshot(run_id)
            if not snap["runs"]:
                raise BudgetStop("unregistered trajectory")
            run = snap["runs"][0]
            if run["fingerprint"] != self.fp or not run["approval"]:
                raise BudgetStop("explicit approval for this exact frozen run required")
            if run["status"] in {"completed", "failed"}:
                return snap
            session = json.loads(run["session"])
            w = CDW(); w.restore(session["environment"])
            pending = [r for r in snap["requests"] if r["status"] in {"reserved","received","ambiguous","billing_mismatch"}]
            if pending and pending[-1]["status"] != "received":
                raise BudgetStop("in-flight/ambiguous request retained; no automatic resend")
            if pending:
                request = pending[-1]
                response = json.loads(request["response"])
            else:
                payload = {"model": self.config["model_id"], "temperature": 0, "max_tokens": 512, "stream": False,
                           "messages": session["messages"], "tools": TOOLS,
                           "tool_choice": {"type":"function","function":{"name":"cdw_action"}}}
                if len(json.dumps(payload, ensure_ascii=False).encode()) + 1024 > 8192:
                    raise BudgetStop("conservative input bound exceeded; no silent truncation")
                amount = self.rates.reserve(8192,512)
                req_id = self.ledger.reserve(run_id, self.fp, session["decisions"]+1, amount, payload)
                started = time.perf_counter()
                try:
                    response = self.transport(payload, send_authorized=True)
                except Exception as exc:
                    response = {"status":None,"body":None,"raw":None,"transport_error":type(exc).__name__}
                response["latency_s"] = time.perf_counter()-started
                usage = calculated = None
                cost_error = None
                try:
                    usage = usage_from(response.get("body"))
                    if usage["input_tokens"] > 8192 or usage["output_tokens"] > 512:
                        raise BudgetStop("observed usage exceeds reserved token bounds")
                    calculated = self.rates.calculated(usage)
                    if calculated is None:
                        raise BudgetStop("cache usage/charging semantics unknown")
                except Exception as exc:
                    cost_error = type(exc).__name__ + ": " + str(exc)
                response["cost_error"] = cost_error
                self.ledger.receive(req_id,response,usage,calculated,valid=cost_error is None)
                request = self.ledger.snapshot(run_id)["requests"][-1]
                if request["status"] != "received":
                    raise BudgetStop("unknown charge/usage: response preserved, reservation retained")
            # Recovery reuses durable response and never repeats its HTTP request.
            before = w.get_observation()
            decision = None
            error = None
            try:
                if response.get("status") != 200:
                    raise ValueError("HTTP failure: " + str(response.get("status")))
                message, call_id, decision = decode_tool(response["body"], self.config["model_id"], w.s["remaining_budget"])
                result = w.step(decision["action"])
                session["messages"].extend([message, {"role":"tool","tool_call_id":call_id,"content":json.dumps(result)}])
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
                result = w.get_observation()
            session["decisions"] += 1
            terminal = bool(w.score()["success"] or session["decisions"] >= 8 or w.s["remaining_budget"] <= 0 or error)
            if terminal and not w.score()["success"] and not error:
                error = "decision/action budget exhausted"
            session.update(environment=w.snapshot(),error=error)
            trajectory = {"step": session["decisions"], "visible_before": before, "action": decision.get("action") if decision else None,
                "tool_result": result, "belief_report": decision.get("belief") if decision else None,
                "plan_snapshot": decision.get("plan") if decision else None,
                "messages":session["messages"], "usage":json.loads(request["usage"]),
                "calculated_micro_cny":request["calculated"],"actual_billed_cny":None,
                "latency_s":response.get("latency_s"), "error":error}
            self.ledger.apply(request["id"],session,trajectory,terminal=terminal,error=error)
            if terminal:
                return self.ledger.snapshot(run_id)


def export(ledger, config, run_id, path):
    path = Path(path); path.mkdir(parents=True,exist_ok=True)
    snap = ledger.snapshot(run_id)
    if not snap["runs"]:
        raise ValueError("unknown run")
    run = snap["runs"][0]; session = json.loads(run["session"])
    w = CDW(); w.restore(session["environment"])
    def write(name, value):
        (path/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    (path/"hidden").mkdir(exist_ok=True)
    write("hidden/session.json",session)
    write("config.yaml",{**config,**{k:session[k] for k in ("task_id","line","source","split","condition","seed","checkpoint_hash")},"frozen_fingerprint":run["fingerprint"]})
    events = [e for e in snap["audit"] if json.loads(e["details"]).get("run") == run_id or json.loads(e["details"]).get("request") in {r["id"] for r in snap["requests"]}]
    with (path/"events.jsonl").open("w",encoding="utf-8") as f:
        for r in snap["requests"]:
            f.write(json.dumps({"event":"request_record",**r},ensure_ascii=False)+"\n")
        for e in events:
            f.write(json.dumps(e,ensure_ascii=False)+"\n")
    with (path/"trajectory.jsonl").open("w",encoding="utf-8") as f:
        applied = set()
        for e in events:
            if e["event"] == "decision_applied":
                f.write(json.dumps(json.loads(e["details"])["trajectory"],ensure_ascii=False)+"\n")
                applied.add(json.loads(e["details"])["request"])
        for r in snap["requests"]:
            if r["id"] not in applied:
                response = json.loads(r["response"]) if r["response"] else {}
                f.write(json.dumps({"step":r["step"],"action":None,"tool_result":None,"status":r["status"],
                    "error":response.get("cost_error") or response.get("transport_error") or "request interrupted; outcome unknown",
                    "usage":json.loads(r["usage"]) if r["usage"] else None,"reserved_micro_cny":r["reserved"],
                    "actual_billed_cny":None if r["billed"] is None else r["billed"]/1e6,
                    "request_record":r["id"]},ensure_ascii=False)+"\n")
    missing = sum(r["billed"] is None for r in snap["requests"])
    metrics = {**w.score(),"decisions":len(snap["requests"]),"applied_decisions":session["decisions"],"status":run["status"],"error":session["error"],"denominator":1,"excluded":False,"source":"SIM",
               "actual_api_cost_cny":None if missing else sum(r["billed"] for r in snap["requests"])/1e6,
               "reserved_exposure_cny":sum(r["reserved"] if r["billed"] is None else r["billed"] for r in snap["requests"])/1e6,
               "unreconciled_requests":missing,"completion_criterion":"correct change applied and verified"}
    write("metrics.json",metrics)
    (path/"report.md").write_text("# 机制 Pilot（不可当作统计显著或 SOTA）\n\n" +
        f"Run {run_id}, source SIM, denominator 1. Status {run['status']}.\n\n"+
        json.dumps(metrics,ensure_ascii=False,indent=2)+"\n\nAll responses/failures retained. Costs remain unknown until reconciled.\n",encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command",choices=["prepare","init-ledger","approve","run","export","reconcile","review","close-uncertain","status"])
    p.add_argument("--config",default="configs/gate1.json")
    p.add_argument("--run-id",choices=[r[0] for r in RUNS],default="g1-01")
    p.add_argument("--require-approval",action="store_true")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--max-spend-cny",type=float,default=8)
    p.add_argument("--evidence-file")
    p.add_argument("--billing-file")
    p.add_argument("--confirm-process-stopped",action="store_true")
    args=p.parse_args()
    config=validate(json.loads(Path(args.config).read_text(encoding="utf-8")))
    if args.max_spend_cny != 8:
        raise BudgetStop("Gate 1 batch ceiling frozen at CNY 8")
    if args.command == "prepare" or args.dry_run:
        print(json.dumps(readiness(config),ensure_ascii=False,indent=2)); return
    if args.command == "init-ledger":
        ledger=Ledger(LEDGER_PATH,create=True)
        for rid,line,task in RUNS:
            ledger.register(rid,fingerprint(config),initial_session(task,line))
        print("Ledger initialized; all runs unapproved."); return
    ledger=Ledger(LEDGER_PATH)
    if args.command in {"approve","review","close-uncertain"}:
        if not args.evidence_file:
            raise BudgetStop("human evidence file required")
        evidence=Path(args.evidence_file).read_text(encoding="utf-8")
        if args.command == "approve":
            previous = {"g1-02":"g1-01","g1-03":"g1-02"}.get(args.run_id)
            ledger.approve(args.run_id,fingerprint(config),evidence,ready=readiness(config)["ready_for_approval"],predecessor=previous)
        elif args.command == "review":
            ledger.review(args.run_id,evidence)
        else:
            ledger.close_uncertain(args.run_id,evidence,process_stopped=args.confirm_process_stopped)
    elif args.command == "reconcile":
        if not args.billing_file:
            raise BudgetStop("billing evidence required")
        bill=json.loads(Path(args.billing_file).read_text(encoding="utf-8"))
        ledger.reconcile(bill["request_id"],micro_cny(bill["actual_cny"]),bill["usage"],bill["evidence"],process_stopped=args.confirm_process_stopped)
    elif args.command == "run":
        if not args.require_approval:
            raise BudgetStop("--require-approval required")
        try:
            Gate1Engine(ledger,config).run(args.run_id)
        finally:
            export(ledger,config,args.run_id,ROOT/"results"/"gate1"/args.run_id)
        print("Single trajectory ended; reconcile bills and review before any next trajectory.")
    elif args.command == "export":
        export(ledger,config,args.run_id,ROOT/"results"/"gate1"/args.run_id)
    elif args.command == "status":
        s=ledger.snapshot(); print(json.dumps({k:s[k] for k in ("exposure_micro_cny","actual_verified_micro_cny","unreconciled_requests")},indent=2))


if __name__ == "__main__":
    main()
