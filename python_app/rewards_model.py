"""Python reward estimates and independent one-gift budget comparisons.

Contribution: AI-assisted migration; actual team owners/reviewers must be filled
in CONTRIBUTIONS.md. Rules are frozen references, not stock or account feeds.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path

RATES = {
    "膠樽 · 80 分／公斤": (80, "kg"),
    "玻璃樽 · 20 分／公斤": (20, "kg"),
    "紙張／金屬／其他塑膠等 · 10 分／公斤": (10, "kg"),
    "四電一腦 · 10 分／件": (10, "piece"),
}


def number(value):
    """Reject non-finite, negative and boolean quantities before arithmetic."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("請輸入有效的非負數。") from None
    if isinstance(value, bool) or not result.is_finite() or not 0 <= result <= Decimal("1e12"):
        raise ValueError("請輸入有效的非負數（不超過 10¹²）。")
    return result


def green_estimate(material, quantity):
    """Estimate the listed weight/piece rate; weight below 0.1 kg earns zero."""
    if material is None:
        return Decimal(0)
    if material not in RATES:
        raise ValueError("請選擇表列回收物。")
    amount = number(quantity)
    rate, unit = RATES[material]
    if unit == "piece" and amount != amount.to_integral_value():
        raise ValueError("件數須為非負整數。")
    return Decimal(0) if unit == "kg" and amount < Decimal("0.1") else amount * rate


def cash_estimate(bottles):
    """Snapshot rule: HK$0.10 each, at most 30 per account/card per day."""
    count = number(bottles)
    if count != count.to_integral_value():
        raise ValueError("樽數須為非負整數。")
    eligible = min(count, Decimal(30))
    return eligible * Decimal("0.10"), int(eligible)


def load_rewards():
    path = Path(__file__).resolve().parent.parent / "data/green_rewards_snapshot.json"
    return json.loads(path.read_text(encoding="utf-8"))


def budget_rewards(existing, earned, *, category="all", descending=True):
    """Rank affordable gifts, then unmet goals; never spend one budget twice."""
    total = number(existing) + number(earned)
    ready, future = [], []
    for gift in load_rewards()["gifts"]:
        if category != "all" and gift["category"] != category:
            continue
        points = Decimal(gift["points"])
        gap = max(Decimal(0), points - total).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        row = dict(gift, gap=gap, after=total-points)
        (ready if points <= total else future).append(row)
    ready.sort(key=lambda gift: gift["points"], reverse=descending)
    future.sort(key=lambda gift: gift["points"])
    return total, ready, future
