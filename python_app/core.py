"""Shared Python data and recommendation algorithms.

Contribution: AI-assisted existing implementation; the team must record actual
primary owners/reviewers in CONTRIBUTIONS.md before submission.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "RecycleMatch_HK_public_points_clean.csv"
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two WGS84 coordinate pairs."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def load_points() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lgt"] = pd.to_numeric(df["lgt"], errors="coerce")
    df = df.dropna(subset=["lat", "lgt"]).copy()
    df["waste_type"] = df["waste_type"].fillna("")
    return df


def find_value(obj: Any, keys: tuple[str, ...]) -> Any:
    """Find a coordinate/address field in common LandsD response shapes."""
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        for value in obj.values():
            found = find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_value(value, keys)
            if found is not None:
                return found
    return None


def request_json(url: str, params: dict[str, str] | None = None) -> Any:
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "RecycleMatch-HK-Student-Project/1.0"})
    with urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def geocode_address(query: str) -> tuple[float, float, str]:
    """Search an HK address and convert the selected HKGRID point to WGS84."""
    result = request_json(
        "https://www.map.gov.hk/gs/api/v1.0.0/locationSearch", {"q": query}
    )
    if isinstance(result, dict):
        candidates = result.get("results") or result.get("data") or result.get("suggestions") or []
        if not candidates and any(k in result for k in ("x", "e", "east", "northing")):
            candidates = [result]
    elif isinstance(result, list):
        candidates = result
    else:
        candidates = []
    if not candidates:
        raise ValueError("地址查詢没有返回结果，请嘗試更完整的香港地址，或手動輸入坐標。")
    place = candidates[0]
    easting = find_value(place, ("x", "e", "east", "easting"))
    northing = find_value(place, ("y", "n", "north", "northing"))
    if easting is None or northing is None:
        raise ValueError("地址结果中没有可用的香港格網坐標。")
    converted = request_json(
        "https://www.geodetic.gov.hk/transform/v2/",
        {"inSys": "hkgrid", "outSys": "wgsgeog", "e": str(easting), "n": str(northing)},
    )
    lat = find_value(converted, ("wgsLat", "latitude", "lat", "LAT", "y"))
    lon = find_value(converted, ("wgsLong", "longitude", "lon", "lng", "LON", "x"))
    if lat is None or lon is None:
        raise ValueError("坐標轉换未返回经纬度。")
    label = str(find_value(place, ("nameZH", "nameEN", "name", "address", "text", "label")) or query)
    return float(lat), float(lon), label


def material_keys(value: str) -> set[str]:
    return {part.strip().casefold() for part in value.split(",") if part.strip()}


def rank_points(
    df: pd.DataFrame, lat: float, lon: float, radius_km: float | None = None
) -> pd.DataFrame:
    distances = [
        haversine_km(lat, lon, float(point_lat), float(point_lon))
        for point_lat, point_lon in zip(df["lat"], df["lgt"])
    ]
    ranked = df.assign(distance_km=distances)
    if radius_km is not None:
        ranked = ranked.loc[ranked["distance_km"] <= radius_km]
    return ranked.sort_values("distance_km", kind="stable").reset_index(drop=True)


def single_stop_plan(ranked: pd.DataFrame, materials: list[str]) -> pd.DataFrame:
    if not materials:
        return ranked
    requested = {material.strip().casefold() for material in materials}
    matches = ranked["waste_type"].map(lambda value: requested <= material_keys(value))
    return ranked.loc[matches].reset_index(drop=True)


def fewer_stop_plan(ranked: pd.DataFrame, materials: list[str]) -> pd.DataFrame:
    """Cover as many remaining materials as possible, breaking ties by distance."""
    if not materials:
        return ranked
    remaining = {material.strip().casefold() for material in materials}
    candidates = list(enumerate(ranked["waste_type"].map(material_keys)))
    chosen: list[int] = []
    while remaining:
        best_idx, best_gain = None, set()
        for idx, accepted in candidates:
            covers = remaining & accepted
            if len(covers) > len(best_gain):
                best_idx, best_gain = idx, covers
        if best_idx is None:
            break
        chosen.append(best_idx)
        remaining.difference_update(best_gain)
    return ranked.iloc[sorted(chosen)].reset_index(drop=True)


def recommend_nearest(df: pd.DataFrame, lat: float, lon: float, materials: list[str]) -> pd.DataFrame:
    return single_stop_plan(rank_points(df, lat, lon), materials)


def recommend_fewer_stops(df: pd.DataFrame, lat: float, lon: float, materials: list[str]) -> pd.DataFrame:
    return fewer_stop_plan(rank_points(df, lat, lon), materials)


def google_maps_walk_url(lat: float, lon: float, dest_lat: float, dest_lon: float) -> str:
    return "https://www.google.com/maps/dir/?" + urlencode(
        {"api": "1", "origin": f"{lat},{lon}", "destination": f"{dest_lat},{dest_lon}", "travelmode": "walking"}
    )


