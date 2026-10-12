import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from adfl.agents.interface import APIAgent, MockAgent, PROMPT, parse_response
from adfl.budget import BudgetGuard, BudgetStop
from adfl.world import CDW
from adfl.evaluation import score_line, attribution_metrics, plan_metrics
from adfl.config import load_config


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class RunLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=False)
        for name in ("trajectory.jsonl", "events.jsonl"):
            (self.path / name).touch()

    def append(self, stream, value):
        with (self.path / (stream + ".jsonl")).open("a", encoding="utf-8") as f:
            f.write(json.dumps(value, ensure_ascii=False) + "\n")
            f.flush()


def fixture(line, variant):
    family = {"p1": "attribution", "p2": "plan", "p3": "attribution", "p4": "complement", "p5": "plan"}[line]
    actions = []
    if family == "complement":
        actions.append({"kind": "calibrate"})
    actions.append({"kind": "diagnose"})
    if family in {"plan", "complement"}:
        actions.append({"kind": "prepare"})
    actions.extend([{"kind": "apply_change", "target": "A" if variant == "E" else "B"}, {"kind": "verify"}])
    return family + ":" + variant, actions


def run_episode(path, task_id, agent, line="p1", seed=0, condition="scripted_calibration", source="SIM", guard=None, pricing=None):
    if source not in {"SIM", "OBS", "CF", "ORACLE"}:
        raise ValueError("invalid source")
    if isinstance(agent, MockAgent) and source != "SIM":
        raise ValueError("scripted calibration must be SIM")
    log = RunLog(path)
    world = CDW()
    obs = world.reset(task_id, seed)
    checkpoint = world.snapshot()
    gt_path = log.path / "hidden" / "initial.json"
    gt_path.parent.mkdir()
    dump(gt_path, checkpoint)
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(obs)}]
    config = dict(task_id=task_id, template_family=task_id.split(":")[0], line=line, source=source,
                  split="calibration", condition=condition, seed=seed, checkpoint_hash=world.checkpoint_hash(),
                  hidden_gt_path="hidden/initial.json", model=asdict(agent.config) if isinstance(agent, APIAgent) else "Mock",
                  prompt_hash=hashlib.sha256(PROMPT.encode()).hexdigest(), action_budget=12,
                  test_tuning=False, automatic_retries=0, pricing=asdict(pricing) if pricing else None)
    # JSON is valid YAML 1.2; avoids an unnecessary YAML dependency.
    dump(log.path / "config.yaml", config)
    error = None
    reports = []
    try:
        while not obs["completed"] and world.s["remaining_budget"]:
            started = time.perf_counter()
            usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
            cost = 0
            if isinstance(agent, APIAgent):
                if guard is None or pricing is None or agent.transport is None or agent.config.model_id == "unselected":
                    raise BudgetStop("transport, verified pricing, selected model and approval required")
                request = agent.request(messages)
                # UTF-8 byte count plus explicit overhead is a deliberately loose input upper bound.
                bound = len(json.dumps(request, ensure_ascii=False).encode()) + 1024
                reservation = pricing.estimate(bound, agent.config.max_tokens)
                guard.reserve(reservation)
                dump(log.path / "budget.json", guard.state())
                log.append("events", {"event": "request_reserved", "request": request, "reservation_cny": reservation})
                try:
                    response = agent.transport(request)
                except Exception:
                    guard.settle(None, None)
                    raise
                usage, cost = response.get("usage"), response.get("billed_cny")
                log.append("events", {"event": "response", "raw_response": response})
                guard.settle(cost, usage)
                dump(log.path / "budget.json", guard.state())
                decision = parse_response(response["text"])
            else:
                decision = agent.act(messages)
            reports.append({k: decision.get(k) for k in ("belief", "plan")})
            action = decision["action"]
            before = obs
            obs = world.step(action)
            messages.append({"role": "assistant", "content": json.dumps(decision)})
            messages.append({"role": "user", "content": json.dumps(obs)})
            log.append("trajectory", {"step": len(reports), "visible_before": before, "action": action,
                                      "tool_result": obs, "belief_report": decision.get("belief"),
                                      "plan_snapshot": decision.get("plan"), "messages": messages.copy(),
                                      "latency_s": time.perf_counter() - started, "usage": usage, "cost_cny": cost})
            dump(log.path / "hidden" / "session.json", {"environment": world.snapshot(),
                 "messages": messages, "agent_fingerprint": agent.fingerprint() if isinstance(agent, APIAgent) else "Mock",
                 "budget": guard.state() if guard else None, "reports": reports})
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)
        log.append("events", {"event": "episode_failed", "error": error, "automatic_retry": False})
    finally:
        if guard:
            dump(log.path / "budget.json", guard.state())
        dump(log.path / "hidden" / "final.json", world.snapshot())
        metrics = {**world.score(), "condition": condition, "source": source, "error": error,
                   "excluded": False, "completion_criterion": "applied target and successful verify", "denominator": 1,
                   "actual_api_cost_cny": guard.spent if guard else 0,
                   "first_two_actions": [h["action"] for h in world.s["history"][:2]]}
        if line == "p1":
            metrics.update(attribution_metrics(None, world.s["root_cause"], world.s["history"]))
        if line == "p4":
            metrics.update(action_cost=metrics["tool_calls"],
                           preparatory_action_selected=any(h["action"]["kind"] == "calibrate" for h in world.s["history"]))
        if line == "p5":
            metrics.update(plan_metrics(world.s["history"], world.s["invalid_nodes"]))
        dump(log.path / "metrics.json", metrics)
        (log.path / "report.md").write_text(
            "# 机制 Pilot（不可当作统计显著或 SOTA）\n\n"
            f"Source: {source}; denominator: 1; success: {metrics['success']}; error: {error}.\n"
            "All failures retained. Scripted outcomes only calibrate tools. No experimental comparison executed.\n", encoding="utf-8")
    return metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="results/gate0")
    p.add_argument("--config", default="configs/gate0.json")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-spend-cny", type=float, default=0)
    p.add_argument("--require-approval", action="store_true")
    args = p.parse_args()
    load_config(Path(args.config))
    root = Path(args.output)
    if args.dry_run:
        print(json.dumps({"network_calls": 0, "approved": False, "estimated_cost": None,
                          "reason": "model/pricing not supplied; see HANDOFF.md scenario envelope",
                          "max_spend_cny": args.max_spend_cny}))
        return
    for line in ("p1", "p2", "p3", "p4", "p5"):
        records = []
        for variant in ("H", "E", "U"):
            task, actions = fixture(line, variant)
            records.append(run_episode(root / line / variant, task, MockAgent(actions), line=line))
        metrics = score_line(line, records)
        metrics["missing_arms"] = ["all scientific comparison arms; calibration only"]
        dump(root / line / "summary.json", metrics)
    print("15 SIM calibration fixtures; real API calls=0, spend CNY=0")


if __name__ == "__main__":
    main()
