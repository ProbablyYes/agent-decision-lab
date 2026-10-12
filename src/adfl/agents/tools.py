"""Gate 1 native tool protocol; does not alter the world or research metrics."""
import json
from adfl.agents.interface import ACTION_SCHEMA, PROMPT

PROMPT_VERSION = "v0.2-native-tools-1"
TOOL_PROMPT = PROMPT + " Use the cdw_action function instead of JSON text. Return exactly one function call per decision. Optional belief/plan remain self-reports, not required measurements."
PRIMITIVE = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": [k for k in ACTION_SCHEMA["kind"] if k != "combo"]},
    "target": {"type": "string", "enum": ["A", "B"]}}, "required": ["kind"], "additionalProperties": False}
MACRO = {"type": "object", "properties": {"kind": {"const": "combo"},
    "actions": {"type": "array", "items": PRIMITIVE, "minItems": 1, "maxItems": 12}},
    "required": ["kind", "actions"], "additionalProperties": False}
TOOLS = [{"type": "function", "function": {"name": "cdw_action",
    "description": "Take a CDW action and receive its observable tool result.",
    "parameters": {"type": "object", "properties": {"action": {"oneOf": [PRIMITIVE, MACRO]},
        "belief": {"type": "string"}, "plan": {"type": "array", "items": {"type": "string"}}},
        "required": ["action"], "additionalProperties": False}}}]


def validate_action(action, remaining):
    if not isinstance(action, dict):
        raise ValueError("action must be object")
    if action.get("kind") == "combo":
        if set(action) != {"kind", "actions"} or not isinstance(action["actions"], list) or not 1 <= len(action["actions"]) <= remaining:
            raise ValueError("macro exceeds remaining primitive budget or has invalid shape")
        for child in action["actions"]:
            if not isinstance(child, dict) or child.get("kind") == "combo":
                raise ValueError("nested/invalid macro")
            validate_action(child, remaining)
        return
    if action.get("kind") not in PRIMITIVE["properties"]["kind"]["enum"] or set(action) - {"kind", "target"}:
        raise ValueError("invalid primitive")
    if remaining < 1:
        raise ValueError("primitive budget exhausted")
    if action.get("kind") == "apply_change" and action.get("target") not in {"A", "B"}:
        raise ValueError("apply_change requires target A or B")
    if "target" in action and action["target"] not in {"A", "B"}:
        raise ValueError("invalid target")


def decode_tool(body, model_id, remaining):
    if body.get("model") != model_id:
        raise ValueError("returned model differs from frozen model; no fallback accepted")
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or choices[0].get("finish_reason") != "tool_calls":
        raise ValueError("expected one completed native tool call; truncation/refusal retained")
    message = choices[0]["message"]
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("exactly one tool call required")
    call = calls[0]
    if call.get("type") != "function" or call.get("function", {}).get("name") != "cdw_action" or not call.get("id"):
        raise ValueError("invalid tool identity")
    decision = json.loads(call["function"]["arguments"])
    if not isinstance(decision, dict) or set(decision) - {"action", "belief", "plan"}:
        raise ValueError("invalid tool arguments")
    if "belief" in decision and not isinstance(decision["belief"], str):
        raise ValueError("belief self-report must be string")
    if "plan" in decision and (not isinstance(decision["plan"], list) or any(not isinstance(x, str) for x in decision["plan"])):
        raise ValueError("plan self-report must be string array")
    validate_action(decision.get("action"), remaining)
    return message, call["id"], decision
