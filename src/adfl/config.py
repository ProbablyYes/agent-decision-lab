import json


def load_config(path):
    c = json.loads(path.read_text(encoding="utf-8"))
    if c.get("protocol") != "V0.2" or c.get("gate") not in range(5):
        raise ValueError("unsupported protocol/gate")
    if c.get("tune_on_test") is not False or c.get("automatic_retries") != 0 or c.get("concurrency") != 1:
        raise ValueError("test tuning, automatic retries and concurrency disabled")
    if c.get("gate") == 0 and (c.get("max_spend_cny") != 0 or c.get("approved") is not False):
        raise ValueError("Gate 0 must spend zero")
    return c
