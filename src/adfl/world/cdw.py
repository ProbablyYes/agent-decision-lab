import copy
import hashlib
import json
import random


class CDW:
    """A resettable repair world. Snapshots are evaluator-only, never observations."""

    def reset(self, task_id, seed=0):
        family, variant = task_id.split(":")
        if family not in {"attribution", "plan", "complement"} or variant not in {"H", "E", "U"}:
            raise ValueError("unknown task")
        self.rng = random.Random(seed)
        self.s = dict(task_id=task_id, family=family, root_cause=variant,
                      execution_fault=variant == "E", observation_reliability=variant != "U",
                      world_state={"prepared": False, "calibrated": False, "applied": False,
                                   "verified": False, "target": "B" if variant != "E" else "A"},
                      plan_DAG={"prepare": [], "apply": ["prepare"], "verify": ["apply"]},
                      remaining_budget=12, history=[], invalid_actions=0, redundant_probes=0,
                      invalid_nodes=["apply", "verify"] if family == "plan" else [])
        self.last = "Service unavailable after attempted change A. Tools: inspect, diagnose, prepare, calibrate, apply_change(A/B), verify, undo, wait. Goal: restore and verify service."
        return self.get_observation()

    def get_observation(self):
        return {"feedback": self.last, "remaining_actions": self.s["remaining_budget"],
                "completed": self.s["world_state"]["verified"]}

    def snapshot(self):
        return copy.deepcopy({"state": self.s, "rng_state": self.rng.getstate(), "last": self.last})

    def restore(self, checkpoint):
        self.s = copy.deepcopy(checkpoint["state"])
        self.rng = random.Random()
        def tuples(x):
            return tuple(map(tuples, x)) if isinstance(x, (tuple, list)) else x
        self.rng.setstate(tuples(checkpoint["rng_state"]))
        self.last = checkpoint["last"]
        return self.get_observation()

    def checkpoint_hash(self):
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()

    def step(self, action):
        if action.get("kind") == "combo":
            actions = action.get("actions")
            if not isinstance(actions, list) or not actions or len(actions) > 12:
                raise ValueError("invalid macro")
            results = []
            for child in actions:
                if child.get("kind") == "combo":
                    raise ValueError("nested macros disabled")
                results.append(self.step(child))
            return {"steps": results, **self.get_observation()}
        if self.s["remaining_budget"] <= 0:
            raise RuntimeError("action budget exhausted")
        kind = action.get("kind")
        if kind not in {"inspect", "diagnose", "prepare", "calibrate", "apply_change", "verify", "undo", "wait"}:
            raise ValueError("unknown action")
        self.s["remaining_budget"] -= 1
        w = self.s["world_state"]
        prior = copy.deepcopy(w)
        invalid_before = self.s["invalid_actions"]
        if kind == "inspect":
            self.last = "Service unavailable." if not w["applied"] else "Change present; verification required."
        elif kind == "prepare":
            w["prepared"] = True
            self.last = "Workspace prepared."
        elif kind == "calibrate":
            w["calibrated"] = True
            self.last = "Diagnostic instrument calibrated; no target identified yet."
        elif kind == "diagnose":
            if self.s["family"] == "complement" and not w["calibrated"]:
                self.last = "Instrument uncalibrated; reading inconclusive."
            elif not self.s["observation_reliability"]:
                self.last = "Conflicting readings: A or B. Evidence insufficient."
            else:
                self.last = f"Required target {w['target']}. " + ("Prior command did not take effect." if self.s["execution_fault"] else "Prior target A is incompatible.")
        elif kind == "apply_change":
            target = action.get("target")
            if target not in {"A", "B"}:
                raise ValueError("target required")
            if self.s["family"] in {"plan", "complement"} and not w["prepared"]:
                self.s["invalid_actions"] += 1
                self.last = "Change rejected: workspace not prepared."
            elif target != w["target"]:
                self.s["invalid_actions"] += 1
                self.last = "Service unavailable."
            else:
                w["applied"] = True
                self.s["execution_fault"] = False
                self.last = "Change applied."
        elif kind == "verify":
            w["verified"] = w["applied"]
            self.last = "Service restored and verified." if w["verified"] else "Service unavailable."
        elif kind == "undo":
            w["applied"] = w["verified"] = False
            self.last = "Change undone; preparation retained."
        else:
            self.last = "No new evidence."
        if kind in {"inspect", "diagnose"} and any(h["action"] == action for h in self.s["history"]):
            self.s["redundant_probes"] += 1
        self.s["history"].append({"action": copy.deepcopy(action), "before": prior, "after": copy.deepcopy(w),
                                   "invalid": self.s["invalid_actions"] > invalid_before})
        return self.get_observation()

    def score(self):
        return {"success": self.s["world_state"]["verified"], "tool_calls": len(self.s["history"]),
                "invalid_actions": self.s["invalid_actions"], "redundant_probes": self.s["redundant_probes"]}
