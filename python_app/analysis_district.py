"""District-level supply profile of public recycling points in Hong Kong.

Summarises, for every district, how many public points exist, how many
material categories they cover, how many distinct material combinations
occur, and how often opening hours are missing. This supports product
decisions (e.g. where coverage is thin) without pretending that point
counts alone measure demand — no population denominator is claimed here.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "RecycleMatch_HK_public_points_clean.csv"


def load_points() -> pd.DataFrame:
    """Load the frozen cleaned dataset with the same conventions as app.py."""
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lgt"] = pd.to_numeric(df["lgt"], errors="coerce")
    df = df.dropna(subset=["lat", "lgt"]).copy()
    df["waste_type"] = df["waste_type"].fillna("")
    return df


def _materials(waste_type: str) -> tuple[str, ...]:
    return tuple(sorted(part.strip() for part in waste_type.split(",") if part.strip()))


def district_summary(points: pd.DataFrame) -> pd.DataFrame:
    """Aggregate supply indicators per district.

    Returns one row per ``district_id`` with:
    point_count, material_categories (union of accepted materials),
    material_combinations (distinct sorted material sets),
    opening_hours_missing (fraction of points with no openhour_tc),
    top_legend (most common legend type).
    """
    rows: list[dict[str, object]] = []
    for district, group in points.groupby("district_id"):
        combos = {_materials(w) for w in group["waste_type"]}
        categories = {item for combo in combos for item in combo}
        legend = group["legend"].dropna()
        rows.append(
            {
                "district_id": district,
                "point_count": int(len(group)),
                "material_categories": int(len(categories)),
                "material_combinations": int(len(combos)),
                "opening_hours_missing": float(group["openhour_tc"].isna().mean()),
                "top_legend": str(legend.mode().iloc[0]) if not legend.empty else "n/a",
            }
        )
    summary = pd.DataFrame(rows).sort_values("point_count", ascending=False).reset_index(drop=True)
    return summary


def format_report(summary: pd.DataFrame) -> str:
    """Human-readable summary of the district supply profile."""
    total_points = int(summary["point_count"].sum())
    districts = int(len(summary))
    most = summary.iloc[0]
    fewest = summary.iloc[-1]
    missing_overall = float(
        summary["point_count"].to_numpy() @ summary["opening_hours_missing"].to_numpy()
    ) / total_points
    lines = [
        f"Districts: {districts} · Total public points: {total_points:,}",
        f"Most points: {most['district_id']} ({most['point_count']:,})",
        f"Fewest points: {fewest['district_id']} ({fewest['point_count']:,})",
        f"Opening hours missing overall: {missing_overall:.1%}",
        f"Material categories across districts: "
        f"{int(summary['material_categories'].min())}–{int(summary['material_categories'].max())}",
    ]
    return "\n".join(lines)
