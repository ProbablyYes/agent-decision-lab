from dataclasses import dataclass
import math


class BudgetStop(RuntimeError):
    pass


@dataclass(frozen=True)
class Pricing:
    input_per_million: float
    output_per_million: float
    currency: str
    cny_per_unit: float
    source: str
    version: str
    fx_time: str

    def estimate(self, input_bound, output_bound):
        numbers = [self.input_per_million, self.output_per_million, self.cny_per_unit, input_bound, output_bound]
        if any(not math.isfinite(n) or n < 0 for n in numbers) or self.cny_per_unit <= 0:
            raise BudgetStop("invalid pricing/token bounds")
        if not all([self.currency, self.source, self.version, self.fx_time]):
            raise BudgetStop("unverified pricing metadata")
        return (input_bound * self.input_per_million + output_bound * self.output_per_million) / 1e6 * self.cny_per_unit


class BudgetGuard:
    def __init__(self, gate=0, approved=False, max_spend_cny=10, spent=0.0):
        if gate not in range(5) or not math.isfinite(spent) or spent < 0 or not math.isfinite(max_spend_cny) or max_spend_cny < 0:
            raise ValueError("invalid budget configuration")
        self.gate, self.approved, self.spent = gate, approved, spent
        self.limit = min([0, 10, 40, 70, 90][gate], max_spend_cny, 90)
        self.pending = None
        self.blocked = False

    def reserve(self, amount):
        if not math.isfinite(amount) or amount < 0:
            raise BudgetStop("invalid reservation")
        if self.blocked or not self.approved or self.gate == 0:
            raise BudgetStop("gate approval required or ledger blocked")
        if self.pending is not None:
            raise BudgetStop("one in-flight request only")
        if self.spent >= self.limit or self.spent + amount > self.limit or self.spent + amount >= 100:
            raise BudgetStop("stage / operating / hard budget limit")
        self.pending = amount

    def settle(self, billed_cny, usage):
        if self.pending is None:
            raise BudgetStop("no reservation")
        reserved = self.pending
        self.pending = None
        if billed_cny is None or not usage or not all(k in usage for k in ("input_tokens", "output_tokens", "cached_tokens")):
            self.spent += reserved
            self.blocked = True
            raise BudgetStop("unknown usage/bill: retain reservation and stop")
        if not math.isfinite(billed_cny) or billed_cny < 0 or any(not isinstance(v, int) or v < 0 for v in usage.values()):
            self.spent += reserved
            self.blocked = True
            raise BudgetStop("invalid bill/usage")
        self.spent += billed_cny
        if billed_cny > reserved or self.spent >= self.limit:
            self.blocked = True

    def state(self):
        return {"gate": self.gate, "limit_cny": self.limit, "spent_cny": self.spent,
                "reserved_cny": self.pending, "blocked": self.blocked,
                "thresholds_reached": [x for x in (10, 40, 90, 100) if self.spent >= x]}
