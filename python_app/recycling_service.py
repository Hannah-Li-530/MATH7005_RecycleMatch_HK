"""UI-independent Python queries and same-origin method comparisons.

Contribution: AI-assisted extraction; record actual primary contributors and
reviewers in CONTRIBUTIONS.md before submission. No HTML or browser scripting.
"""
from functools import lru_cache
import json
from pathlib import Path
import math
import pandas as pd
from core import (load_points, material_keys, rank_points, single_stop_plan,
                  fewer_stop_plan, request_json, find_value)
from reward_schemes import GREEN_TYPES

ROOT = Path(__file__).resolve().parent.parent
LABELS = {
    "metals": "金屬", "paper": "紙張", "plastics": "塑膠", "food waste": "廚餘",
    "rechargeable batteries": "充電池", "plastic bottle": "塑膠瓶",
    "glass bottles": "玻璃瓶", "fluorescent lamp": "螢光燈管", "clothes": "衣物",
    "computers": "電腦", "printer cartridges": "列印機墨盒", "barbeque fork": "燒烤叉",
    "beverage cartons": "飲品紙盒", "regulated electrical equipment": "受管制電器",
    "small electrical and electronic equipment": "小型電器",
}


@lru_cache(maxsize=1)
def points():
    return load_points().fillna("")


@lru_cache(maxsize=1)
def machines():
    snapshot = json.loads((ROOT / "data/epd_rvm_locations_snapshot.json").read_text(encoding="utf-8"))
    return pd.DataFrame(snapshot["machines"]).fillna("")


@lru_cache(maxsize=16)
def ranked_candidates(lat, lon, radius=None, scope="全部回收點", cash=False):
    """Validate origin and filter eligible records before calculating distance."""
    if not (math.isfinite(lat) and math.isfinite(lon) and 22 <= lat <= 22.7 and 113.7 <= lon <= 114.6):
        raise ValueError("請輸入香港範圍內的有效經緯度。")
    if radius not in (None, .5, 1, 3):
        raise ValueError("請選擇有效搜尋範圍。")
    if scope not in ("全部回收點", "只看綠綠賞"):
        raise ValueError("請選擇有效設施範圍。")
    data = machines() if cash else points()
    if not cash and scope == "只看綠綠賞":
        data = data[data.legend.isin(GREEN_TYPES)]
    return rank_points(data, lat, lon, radius)


def query_plan(lat, lon, materials, radius=None, scope="全部回收點", mode="單點最近"):
    """Keep candidate-union coverage distinct from actual returned coverage."""
    wanted = {item.casefold() for item in materials}
    allowed = {item for raw in points().waste_type for item in material_keys(raw)}
    if not wanted or not wanted <= allowed:
        raise ValueError("請至少選擇一種名錄中的回收物。")
    if mode not in ("單點最近", "盡量少跑點"):
        raise ValueError("請選擇有效推薦方式。")
    ranked = ranked_candidates(lat, lon, radius, scope)
    available = set().union(*(material_keys(raw) for raw in ranked.waste_type)) & wanted
    result = (single_stop_plan if mode == "單點最近" else fewer_stop_plan)(ranked, list(wanted))
    covered = set().union(*(material_keys(raw) for raw in result.waste_type)) & wanted
    return dict(ranked=ranked, result=result, available=available, covered=covered,
                missing=wanted-available, result_missing=wanted-covered)


def compare_plans(lat, lon, materials, radius=None, scope="全部回收點"):
    """Recompute all three plans for the exact same request and candidate pool."""
    ranked = ranked_candidates(lat, lon, radius, scope)
    wanted = {item.casefold() for item in materials}
    keys = ranked.waste_type.map(material_keys)
    nearest = set()
    for item in wanted:
        found = keys[keys.map(lambda accepted: item in accepted)]
        if not found.empty:
            nearest.add(found.index[0])
    plans = {"逐項最近，再去重": ranked.loc[sorted(nearest)],
             "最近單點": single_stop_plan(ranked, list(wanted)).head(1),
             "貪心多點": fewer_stop_plan(ranked, list(wanted))}
    rows = []
    for method, frame in plans.items():
        covered = set().union(*(material_keys(raw) for raw in frame.waste_type)) & wanted
        rows.append({"方法": method, "停靠數": len(frame), "覆蓋類別": f"{len(covered)}/{len(wanted)}",
                     "最遠站點距起點（km）": round(frame.distance_km.max(), 3) if len(frame) else None})
    return pd.DataFrame(rows), plans


def search_places(query):
    """Return candidate addresses; never silently use an unrelated first hit."""
    if not 2 <= len(query.strip()) <= 120:
        raise ValueError("請輸入 2–120 個字符的香港地點。")
    raw = request_json("https://www.map.gov.hk/gs/api/v1.0.0/locationSearch", {"q": query.strip()})
    data = raw if isinstance(raw, list) else raw.get("results") or raw.get("data") or raw.get("suggestions") or []
    return [p for p in data if isinstance(p, dict) and p.get("x") is not None and p.get("y") is not None][:8]


def place_coordinates(place):
    """Convert the explicitly selected LandsD candidate to WGS84."""
    raw = request_json("https://www.geodetic.gov.hk/transform/v2/",
                       {"inSys": "hkgrid", "outSys": "wgsgeog", "e": str(place["x"]), "n": str(place["y"])})
    lat = float(find_value(raw, ("wgsLat", "latitude", "lat")))
    lon = float(find_value(raw, ("wgsLong", "longitude", "lon", "lng")))
    if not (22 <= lat <= 22.7 and 113.7 <= lon <= 114.6):
        raise ValueError("地點不在香港坐標範圍內。")
    return lat, lon
