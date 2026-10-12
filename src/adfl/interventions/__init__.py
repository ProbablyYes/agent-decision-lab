import copy


def feedback(messages, role, fact):
    """Only carrier changes; no extra observation or environment step."""
    if role not in {"user", "tool", "memory"}:
        raise ValueError("unsupported feedback carrier")
    if role == "memory":
        raise NotImplementedError("Memory carrier is a later independent factor")
    result = copy.deepcopy(messages)
    # Tool carrier requires a matched synthetic tool-call history in both arms.
    result.append({"role": role, "content": fact, **({"tool_call_id": "feedback-1"} if role == "tool" else {})})
    return result


def fork(world, checkpoint, messages):
    world.restore(checkpoint)
    return copy.deepcopy(messages)
