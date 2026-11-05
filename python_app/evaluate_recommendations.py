"""Reproduce the fixed-scenario benchmark using the shipped point snapshot."""
from itertools import combinations
from pathlib import Path

import pandas as pd

from core import fewer_stop_plan, load_points, material_keys, rank_points, single_stop_plan

OUTPUT = Path(__file__).resolve().parent.parent / "analysis_waste" / "recommendation_results.csv"
# Fixed representative starting coordinates, not sampled user trips.
ORIGINS = [
    ("九龍塘", 22.340947, 114.179515), ("中環", 22.2819, 114.1582),
    ("沙田", 22.3827, 114.1889), ("屯門", 22.3951, 113.9734),
    ("東涌", 22.2893, 113.9414),
]
BUNDLES = [
    ["metals", "paper", "plastics"], ["glass bottles", "food waste"],
    ["clothes", "plastic bottle", "rechargeable batteries"],
    ["beverage cartons", "fluorescent lamp", "small electrical and electronic equipment"],
]


def evaluate():
    points = load_points()
    rows = []
    for origin, lat, lon in ORIGINS:
        for radius in (0.5, 1, 3):
            ranked = rank_points(points, lat, lon, radius)
            accepted = ranked.waste_type.map(material_keys)
            for materials in BUNDLES:
                wanted = set(materials)
                masks = {frozenset(wanted & keys) for keys in accepted} - {frozenset()}
                available = set().union(*masks)
                # Identical coverage sets are interchangeable for minimum stop count.
                optimum = next((k for k in range(len(available) + 1)
                                if any(set().union(*group) == available
                                       for group in combinations(masks, k))))
                nearest = set()
                for material in materials:
                    match = accepted[accepted.map(lambda keys: material in keys)]
                    if not match.empty:
                        nearest.add(match.index[0])
                plans = {
                    "逐项最近": ranked.loc[sorted(nearest)],
                    "最近單點": single_stop_plan(ranked, materials).head(1),
                    "贪心多點": fewer_stop_plan(ranked, materials),
                }
                for method, plan in plans.items():
                    covered = set().union(*(material_keys(value) for value in plan.waste_type)) & wanted
                    if method != "最近單點":
                        assert covered == available and len(plan) >= optimum
                    rows.append(dict(origin=origin, radius_km=radius, materials=", ".join(materials),
                                     method=method, requested=len(wanted), covered=len(covered),
                                     available=len(available), stops=len(plan),
                                     farthest_km=round(plan.distance_km.max(), 3) if len(plan) else None,
                                     minimum_stops_for_available=optimum))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    evaluate().to_csv(OUTPUT, index=False)
