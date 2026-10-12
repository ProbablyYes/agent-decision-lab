from dataclasses import dataclass, asdict
import hashlib
import json

PROMPT = 'Restore and verify service. Return JSON {"action":{"kind":"...","target":"A or B for apply_change"}}. Available kinds: inspect, diagnose, prepare, calibrate, apply_change, verify, undo, wait, combo. A combo contains an actions array of primitive actions, each charged separately. Optional belief and plan are self-reports. Do not infer privileged evaluator state.'
ACTION_SCHEMA = {"kind": ["inspect", "diagnose", "prepare", "calibrate", "apply_change", "verify", "undo", "wait", "combo"], "target": ["A", "B"]}


@dataclass(frozen=True)
class FrozenConfig:
    model_provider: str = "unselected"
    model_id: str = "unselected"
    model_revision: str = "unavailable"
    temperature: float = 0.0
    max_tokens: int = 512
    prompt_version: str = "v0.2-instrument-1"


def parse_response(raw):
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("action"), dict):
        raise ValueError("response must contain action object")
    if value["action"].get("kind") not in ACTION_SCHEMA["kind"]:
        raise ValueError("invalid action kind")
    return value


class MockAgent:
    def __init__(self, actions):
        self.actions = iter(actions)

    def act(self, messages):
        return {"action": next(self.actions)}


class APIAgent:
    """Frozen request interface; only an injected transport can send requests.

    No HTTP transport is shipped at Gate 0, so accidental network calls are impossible.
    A transport must return text, usage, and billed_cny, even for billed failures.
    """
    def __init__(self, config=FrozenConfig(), transport=None):
        self.config, self.transport = config, transport

    def request(self, messages):
        return {"model": self.config.model_id, "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens, "messages": messages,
                "response_format": {"type": "json_object"}}

    def fingerprint(self):
        return hashlib.sha256(json.dumps({"config": asdict(self.config), "prompt": PROMPT,
                                          "schema": ACTION_SCHEMA}, sort_keys=True).encode()).hexdigest()
