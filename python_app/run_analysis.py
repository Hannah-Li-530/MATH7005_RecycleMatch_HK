"""Run the project's data-mining analyses on the frozen cleaned dataset.

Produces (in ``python_app/output/``):
    frequent_itemsets.csv        Apriori frequent material combinations
    association_rules.csv        Rules with confidence >= min_confidence
    district_supply_summary.csv  Per-district supply indicators
    analysis_report.txt          Human-readable summary of all results

Run from the python_app folder:
    E:\\py\\python.exe run_analysis.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from apriori import apriori, load_transactions  # noqa: E402
from analysis_district import (  # noqa: E402
    district_summary,
    format_report,
    load_points,
)

MIN_SUPPORT = 0.02      # an itemset must occur in >= 2% of points (~117 of 5,868)
MIN_CONFIDENCE = 0.60   # association-rule confidence threshold
OUT_DIR = Path(__file__).resolve().parent / "output"


def _sorted_items(itemset) -> str:
    return ", ".join(sorted(itemset))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    points = load_points()

    # ---- Apriori material-combination mining -------------------------------
    transactions = load_transactions(points["waste_type"])
    frequent, rules = apriori(transactions, MIN_SUPPORT, MIN_CONFIDENCE)

    itemset_rows = [
        {
            "itemset": _sorted_items(its),
            "size": len(its),
            "support": round(support, 4),
            "count": int(round(support * len(transactions))),
        }
        for its, support in sorted(
            frequent.items(), key=lambda kv: (-kv[1], len(kv[0]))
        )
    ]
    itemsets_df = pd.DataFrame(itemset_rows)
    itemsets_df.to_csv(OUT_DIR / "frequent_itemsets.csv", index=False, encoding="utf-8-sig")

    rule_rows = [
        {
            "antecedent": _sorted_items(rule["antecedent"]),
            "consequent": _sorted_items(rule["consequent"]),
            "support": round(float(rule["support"]), 4),
            "confidence": round(float(rule["confidence"]), 4),
            "lift": round(float(rule["lift"]), 4),
        }
        for rule in rules
    ]
    rules_df = (
        pd.DataFrame(rule_rows)
        .sort_values(["confidence", "support"], ascending=False)
        .reset_index(drop=True)
    )
    rules_df.to_csv(OUT_DIR / "association_rules.csv", index=False, encoding="utf-8-sig")

    # ---- District supply profile -------------------------------------------
    summary = district_summary(points)
    summary.to_csv(OUT_DIR / "district_supply_summary.csv", index=False, encoding="utf-8-sig")

    # ---- Report -------------------------------------------------------------
    top_itemsets = itemsets_df.head(12)
    top_rules = rules_df.head(12)
    lines = [
        "RecycleMatch HK — analysis report",
        "Dataset: RecycleMatch_HK_public_points_clean.csv (frozen)",
        f"Points with coordinates: {len(points):,} · Transactions: {len(transactions):,}",
        f"Apriori min_support={MIN_SUPPORT}, min_confidence={MIN_CONFIDENCE}",
        "",
        f"Frequent itemsets found: {len(itemsets_df):,} "
        f"(including {int((itemsets_df['size'] >= 2).sum()):,} of size >= 2)",
        "",
        "Top frequent itemsets by support:",
        top_itemsets.to_string(index=False),
        "",
        f"Association rules found: {len(rules_df):,}",
        "",
        "Top rules by confidence:",
        top_rules.to_string(index=False),
        "",
        "District supply profile:",
        format_report(summary),
        "",
        "Top 5 districts by point count:",
        summary.head(5)[["district_id", "point_count", "material_categories",
                         "material_combinations", "opening_hours_missing"]].to_string(index=False),
        "",
        "Bottom 5 districts by point count:",
        summary.tail(5)[["district_id", "point_count", "material_categories",
                         "material_combinations", "opening_hours_missing"]].to_string(index=False),
        "",
        "Files written to python_app/output/.",
    ]
    report_text = "\n".join(lines)
    (OUT_DIR / "analysis_report.txt").write_text(report_text, encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()
