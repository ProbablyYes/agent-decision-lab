def paired_intervention(baseline, intervention):
    """One checkpoint is one paired unit; keep harms and recoveries separately."""
    if baseline["checkpoint_hash"] != intervention["checkpoint_hash"]:
        raise ValueError("unmatched checkpoints")
    return {"paired_success_delta": int(intervention["success"]) - int(baseline["success"]),
            "extra_cost": intervention["cost"] - baseline["cost"],
            "harm": bool(baseline["success"] and not intervention["success"]),
            "recovery": bool(not baseline["success"] and intervention["success"])}


def attribution_metrics(reported, truth, history):
    if truth not in {"H", "E", "U"}:
        raise ValueError("invalid evaluator truth")
    actions = [h["action"] for h in history]
    return {"attribution_correct": None if reported is None else reported == truth,
            "invalid_retries": sum(actions[i] == actions[i-1] and actions[i].get("kind") == "apply_change"
                                   for i in range(1, len(actions)))}


def plan_metrics(history, invalid_nodes, original_nodes=None, retained_nodes=None):
    invalid = sum(h["action"].get("kind") == "apply_change" and h["invalid"] for h in history)
    apply_count = sum(h["action"].get("kind") == "apply_change" for h in history)
    valid = set(original_nodes or []) - set(invalid_nodes)
    retention = len(valid & set(retained_nodes)) / len(valid) if retained_nodes is not None and valid else None
    return {"invalid_action_rate": invalid / apply_count if apply_count else None,
            "valid_node_retention": retention,
            "repair_cost": len(history), "completion": bool(history and history[-1]["after"]["verified"])}


def score_line(line, records):
    """Evaluator consumes explicitly collected measurements, never guesses beliefs."""
    if line not in {"p1", "p2", "p3", "p4", "p5"} or not records:
        raise ValueError("line/records required")
    groups = {}
    for r in records:
        groups.setdefault(r["condition"], []).append(r)
    result = {"line": line, "n": len(records), "sampling_unit": "fixture (SIM)",
              "groups": {g: {"n": len(rs), "successes": sum(bool(r["success"]) for r in rs)} for g, rs in groups.items()},
              "primary": "final_success", "missing_arms": [], "scientific_inference": False}
    fields = {"p1": ["attribution_correct", "diagnostic_value", "invalid_retries", "cost"],
              "p2": ["reception", "belief_adoption", "plan_change", "action_change", "first_two_actions", "cost"],
              "p3": ["paired_success_delta", "extra_cost", "harm", "recovery"],
              "p4": ["return", "action_cost", "redundant_probes", "preparatory_action_selected", "regret"],
              "p5": ["invalid_action_rate", "valid_node_retention", "repair_cost", "completion"]}[line]
    result["measurements"] = [{f: r.get(f) for f in fields} for r in records]
    result["unmeasured"] = [f for f in fields if any(r.get(f) is None for r in records)]
    return result
