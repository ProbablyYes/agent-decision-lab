"""Exact decimal accounting. Catalog values are USD/token, not USD/million."""
from decimal import Decimal, ROUND_CEILING
from adfl.budget.guard import BudgetStop


def decimal(value):
    try:
        d = Decimal(str(value))
    except Exception as exc:
        raise BudgetStop("missing/invalid monetary value") from exc
    if not d.is_finite() or d < 0:
        raise BudgetStop("negative/nonfinite monetary value")
    return d


def micro_cny(value):
    return int((decimal(value) * 1000000).to_integral_value(rounding=ROUND_CEILING))


def usage_from(body):
    u = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(u, dict):
        raise BudgetStop("usage unavailable; cannot assume zero")
    p, o = u.get("prompt_tokens"), u.get("completion_tokens")
    details = u.get("prompt_tokens_details") or {}
    c = details.get("cached_tokens")
    write = details.get("cache_write_tokens", u.get("cache_creation_input_tokens"))
    for n in (p, o):
        if type(n) is not int or n < 0:
            raise BudgetStop("invalid input/output usage")
    for n in (c, write):
        if n is not None and (type(n) is not int or n < 0 or n > p):
            raise BudgetStop("invalid cache usage")
    if c is not None and write is not None and c + write > p:
        raise BudgetStop("cache counters exceed prompt tokens")
    total = u.get("total_tokens")
    if total is not None and total != p + o:
        raise BudgetStop("inconsistent total tokens")
    return {"input_tokens": p, "output_tokens": o, "cached_tokens": c, "cache_write_tokens": write}


class RateCard:
    def __init__(self, config):
        self.config = config
        if config.get("currency") != "USD":
            raise BudgetStop("catalog currency not verified as USD")
        self.fx = decimal(config.get("cny_per_usd"))
        if not self.fx:
            raise BudgetStop("FX must be positive")
        self.rates = {k: None if config.get(k) is None else decimal(config[k]) for k in ("input", "output", "cache_read", "cache_write")}
        if self.rates["input"] is None or self.rates["output"] is None:
            raise BudgetStop("input/output price unknown")

    def reserve(self, inputs, outputs):
        if type(inputs) is not int or type(outputs) is not int or min(inputs, outputs) < 0:
            raise BudgetStop("invalid token bounds")
        # Unknown write rates cannot be silently ignored in a conservative reservation.
        if self.rates["cache_read"] is None or self.rates["cache_write"] is None:
            raise BudgetStop("cache tariff incomplete")
        highest = max(self.rates[k] for k in ("input", "cache_read", "cache_write"))
        # Reserve normal input plus possible cache-write surcharge, with 2x contingency.
        usd = (inputs * (self.rates["input"] + highest) + outputs * self.rates["output"]) / 1000000
        return micro_cny(usd * self.fx * 2)

    def calculated(self, usage):
        p, o, c, w = (usage[k] for k in ("input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens"))
        if c is None or w is None:
            return None  # Missing counters are unknown, never inferred as zero.
        if self.rates["cache_read"] is None or self.rates["cache_write"] is None:
            return None
        if self.config.get("cache_write_semantics") != "exclusive_prompt_subset":
            return None
        usd = ((p-c-w)*self.rates["input"] + c*self.rates["cache_read"] + w*self.rates["cache_write"] + o*self.rates["output"]) / 1000000
        return micro_cny(usd * self.fx)
