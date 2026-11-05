"""Small-sample verification tests for RecycleMatch HK core functions.

Covers: Haversine distance (zero / known range / symmetry), material
filtering in ``recommend_nearest`` (matching, ranking, no-match), greedy
behaviour in ``recommend_fewer_stops`` (tie-breaking by distance, duplicate
materials, no-match, full coverage), the hand-written Apriori on a
hand-computable example, and district aggregation.

Run from the python_app folder:
    E:\\py\\python.exe test_recyclematch.py
Prints PASS/FAIL per case; exits non-zero if any case fails.
"""

from __future__ import annotations

import sys

import pandas as pd

from analysis_district import district_summary
from apriori import apriori, load_transactions
from core import haversine_km, recommend_fewer_stops, recommend_nearest
from recycling_service import machines, points, ranked_candidates
from rewards_model import load_rewards

_PASSED = 0
_FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _PASSED, _FAILED
    if condition:
        _PASSED += 1
        print(f"PASS  {name}")
    else:
        _FAILED += 1
        print(f"FAIL  {name}  {detail}")


def points_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_haversine() -> None:
    # Zero distance at the same coordinate.
    check("haversine zero distance", haversine_km(22.30, 114.10, 22.30, 114.10) == 0.0)

    # Known reference pair: HKU station vs Central, expected roughly 2-3 km.
    d = haversine_km(22.2838, 114.1359, 22.2819, 114.1583)
    check("haversine HKU-Central ~2-3 km", 2.0 <= d <= 3.0, f"got {d:.3f}")

    # Symmetry.
    d1 = haversine_km(22.30, 114.10, 22.31, 114.11)
    d2 = haversine_km(22.31, 114.11, 22.30, 114.10)
    check("haversine symmetric", abs(d1 - d2) < 1e-9)


def test_recommend_nearest() -> None:
    df = points_df(
        [
            {"cp_id": 1, "lat": 22.3000, "lgt": 114.1000, "waste_type": "Metals,Paper"},
            {"cp_id": 2, "lat": 22.3100, "lgt": 114.1000, "waste_type": "Paper"},
            {"cp_id": 3, "lat": 22.3000, "lgt": 114.1100, "waste_type": "Plastics"},
        ]
    )

    # Filtering: only points that accept Paper, ranked by distance.
    res = recommend_nearest(df, 22.30, 114.10, ["Paper"])
    check("nearest filters by material", list(res["cp_id"]) == [1, 2], str(list(res["cp_id"])))
    check("nearest ranks by distance", list(res["cp_id"]) == [1, 2] and res.iloc[0]["distance_km"] < res.iloc[1]["distance_km"])

    # Case-insensitive material match.
    res_lower = recommend_nearest(df, 22.30, 114.10, ["paper"])
    check("nearest case-insensitive", list(res_lower["cp_id"]) == [1, 2])

    # No match returns an empty frame (with distance column present).
    res_none = recommend_nearest(df, 22.30, 114.10, ["Clothes"])
    check("nearest no-match empty", len(res_none) == 0 and "distance_km" in res_none.columns)


def test_fewer_stops_tie_by_distance() -> None:
    # Two candidate points each cover exactly one remaining material;
    # the closer one must be picked first.
    df = points_df(
        [
            {"cp_id": 1, "lat": 22.3000, "lgt": 114.1000, "waste_type": "Paper"},
            {"cp_id": 2, "lat": 22.3100, "lgt": 114.1000, "waste_type": "Metals"},
            {"cp_id": 3, "lat": 22.3050, "lgt": 114.1000, "waste_type": "Plastics"},
        ]
    )
    res = recommend_fewer_stops(df, 22.30, 114.10, ["Paper", "Metals"])
    chosen = list(res["cp_id"])
    check("tie-breaking picks both, closer first",
          chosen == [1, 2], f"chosen={chosen}")
    check("tie-breaking distance order",
          res.iloc[0]["distance_km"] < res.iloc[1]["distance_km"])


def test_fewer_stops_duplicate_materials() -> None:
    df = points_df(
        [
            {"cp_id": 1, "lat": 22.3000, "lgt": 114.1000, "waste_type": "Paper,Metals"},
        ]
    )
    res = recommend_fewer_stops(df, 22.30, 114.10, ["Paper", "paper", "PAPER"])
    check("duplicate materials collapse to one", len(res) == 1 and list(res["cp_id"]) == [1])


def test_fewer_stops_no_match() -> None:
    df = points_df(
        [
            {"cp_id": 1, "lat": 22.3000, "lgt": 114.1000, "waste_type": "Paper"},
        ]
    )
    res = recommend_fewer_stops(df, 22.30, 114.10, ["Clothes"])
    check("fewer-stops no-match empty", len(res) == 0)


def test_fewer_stops_full_coverage() -> None:
    # Three materials covered by two stops: one point takes two materials.
    df = points_df(
        [
            {"cp_id": 1, "lat": 22.3000, "lgt": 114.1000, "waste_type": "Paper,Metals"},
            {"cp_id": 2, "lat": 22.3010, "lgt": 114.1010, "waste_type": "Plastics"},
        ]
    )
    res = recommend_fewer_stops(df, 22.30, 114.10, ["Paper", "Metals", "Plastics"])
    check("full coverage with two stops", len(res) == 2 and set(res["cp_id"]) == {1, 2})
    covered = {
        m for _, r in res.iterrows() for m in ["paper", "metals", "plastics"]
        if m in str(r["waste_type"]).lower()
    }
    check("all materials covered", covered == {"paper", "metals", "plastics"}, str(covered))


def test_apriori_hand_example() -> None:
    # Hand-computable case: 4 transactions, min_support = 0.5 -> count >= 2.
    transactions = [
        frozenset({"a", "b", "c"}),
        frozenset({"a", "b"}),
        frozenset({"a", "c"}),
        frozenset({"b", "c"}),
    ]
    frequent, _rules = apriori(transactions, min_support=0.5)
    expected = {
        frozenset({"a"}): 0.75,
        frozenset({"b"}): 0.75,
        frozenset({"c"}): 0.75,
        frozenset({"a", "b"}): 0.5,
        frozenset({"a", "c"}): 0.5,
        frozenset({"b", "c"}): 0.5,
    }
    check("apriori finds 6 frequent itemsets", len(frequent) == 6, str(len(frequent)))
    check("apriori supports match hand computation",
          all(abs(frequent[k] - v) < 1e-9 for k, v in expected.items()))
    # The 3-itemset {a,b,c} occurs once (0.25) and must be pruned.
    check("apriori prunes infrequent 3-itemset", frozenset({"a", "b", "c"}) not in frequent)

    # Rules: a -> b confidence = 0.5 / 0.75 = 2/3 < 0.7 -> none at 0.7.
    _, rules_high = apriori(transactions, min_support=0.5, min_confidence=0.7)
    check("apriori confidence threshold respected", len(rules_high) == 0)
    # At 0.6 every 2-itemset yields two rules (each single removal).
    _, rules_low = apriori(transactions, min_support=0.5, min_confidence=0.6)
    check("apriori generates rules below threshold", len(rules_low) == 6, str(len(rules_low)))


def test_load_transactions() -> None:
    tx = load_transactions(pd.Series(["Metals, Paper", "Paper", "", "  Plastics  ,paper"]))
    check("transactions parse and normalize",
          len(tx) == 3 and tx[0] == frozenset({"metals", "paper"}) and tx[2] == frozenset({"plastics", "paper"}))


def test_district_summary() -> None:
    df = points_df(
        [
            {"district_id": "Kwai_Tsing", "waste_type": "Metals,Paper", "openhour_tc": None, "legend": "Bin"},
            {"district_id": "Kwai_Tsing", "waste_type": "Paper", "openhour_tc": "08:00", "legend": "Bin"},
            {"district_id": "Central_Western", "waste_type": "Plastics", "openhour_tc": None, "legend": "Bin"},
        ]
    )
    summary = district_summary(df).set_index("district_id")
    check("district summary point counts",
          summary.loc["Kwai_Tsing", "point_count"] == 2 and summary.loc["Central_Western", "point_count"] == 1)
    check("district summary categories",
          summary.loc["Kwai_Tsing", "material_categories"] == 2)
    check("district summary combinations",
          summary.loc["Kwai_Tsing", "material_combinations"] == 2)
    check("district summary missing-hours ratio",
          abs(summary.loc["Kwai_Tsing", "opening_hours_missing"] - 0.5) < 1e-9)


def test_utf8_snapshots_and_cached_rankings() -> None:
    # Both snapshots contain Traditional Chinese and must be read as UTF-8 on Windows.
    check("public-point snapshot loads all rows", len(points()) == 5868, str(len(points())))
    check("RVM UTF-8 snapshot loads all machines", len(machines()) == 120, str(len(machines())))
    check("reward UTF-8 snapshot loads all gifts", len(load_rewards()["gifts"]) == 14,
          str(len(load_rewards()["gifts"])))
    first = ranked_candidates(22.372762, 114.178690, 1)
    second = ranked_candidates(22.372762, 114.178690, 1)
    check("cached rankings preserve the same order",
          list(first.cp_id.head(5)) == list(second.cp_id.head(5)))


def main() -> None:
    test_haversine()
    test_recommend_nearest()
    test_fewer_stops_tie_by_distance()
    test_fewer_stops_duplicate_materials()
    test_fewer_stops_no_match()
    test_fewer_stops_full_coverage()
    test_apriori_hand_example()
    test_load_transactions()
    test_district_summary()
    test_utf8_snapshots_and_cached_rankings()
    print(f"\n{_PASSED} passed, {_FAILED} failed")
    sys.exit(1 if _FAILED else 0)


if __name__ == "__main__":
    main()
