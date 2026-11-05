"""Reproduce Apriori threshold and facility-mix sensitivity diagnostics.

Contribution: AI-assisted; actual owners/reviewers to be recorded in
CONTRIBUTIONS.md. A record is a facility listing, not a user's recycling trip.
"""
from pathlib import Path
import pandas as pd
from apriori import apriori, load_transactions
from core import load_points, material_keys

OUT = Path(__file__).resolve().parent / "output"


def rule_metrics(transactions, antecedent, consequent):
    """Exact unrounded support, confidence and lift; missing denominators are NA."""
    n = len(transactions)
    n_a = sum(antecedent <= t for t in transactions)
    n_b = sum(consequent <= t for t in transactions)
    n_ab = sum(antecedent | consequent <= t for t in transactions)
    confidence = n_ab / n_a if n_a else None
    return {"records": n, "antecedent_count": n_a, "both_count": n_ab,
            "support": n_ab / n if n else None, "confidence": confidence,
            "lift": confidence / (n_b / n) if n_b and n and confidence is not None else None}


def build_review():
    """Use a declared 3×3 threshold grid and the same fixed snapshot throughout."""
    points = load_points().fillna("")
    transactions = load_transactions(points.waste_type)
    sensitivity = []
    for support in (.01, .02, .05):
        frequent, rules = apriori(transactions, support, .6)
        for confidence in (.6, .8, .9):
            selected = [r for r in rules if r["confidence"] >= confidence]
            readable = [r for r in selected if len(r["antecedent"]) <= 2 and r["lift"] > 1]
            sensitivity.append({"min_support": support, "min_confidence": confidence,
                                "frequent_itemsets": len(frequent), "rules": len(selected),
                                "short_positive_rules": len(readable)})
    pairs = [(frozenset({"paper"}), frozenset({"metals"})),
             (frozenset({"glass bottles"}), frozenset({"paper"}))]
    profiles, weighting = [], []
    for a, b in pairs:
        rule = f"{', '.join(sorted(a))} → {', '.join(sorted(b))}"
        for legend, frame in [("All records", points), *list(points.groupby("legend", sort=True))]:
            profiles.append({"rule": rule, "facility_type": legend,
                             **rule_metrics(load_transactions(frame.waste_type), a, b)})
        # Reweighting diagnostic: each distinct material-set counts once.
        # Its denominator is patterns, so it is NOT a facility probability.
        unique = sorted(set(transactions), key=lambda t: tuple(sorted(t)))
        for unit, data in [("facility records", transactions), ("unique material patterns", unique)]:
            weighting.append({"rule": rule, "unit": unit, **rule_metrics(data, a, b)})
    return pd.DataFrame(sensitivity), pd.DataFrame(profiles), pd.DataFrame(weighting)


def main():
    OUT.mkdir(exist_ok=True)
    for name, table in zip(("apriori_sensitivity", "rule_facility_profile", "rule_pattern_weighting"), build_review()):
        table.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(name, len(table), "rows")


if __name__ == "__main__":
    main()
