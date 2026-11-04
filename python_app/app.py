"""RecycleMatch HK: a small Streamlit decision-support prototype."""

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
        raise ValueError("地址查询没有返回结果，请尝试更完整的香港地址，或手动输入坐标。")
    place = candidates[0]
    easting = find_value(place, ("x", "e", "east", "easting"))
    northing = find_value(place, ("y", "n", "north", "northing"))
    if easting is None or northing is None:
        raise ValueError("地址结果中没有可用的香港格网坐标。")
    converted = request_json(
        "https://www.geodetic.gov.hk/transform/v2/",
        {"inSys": "hkgrid", "outSys": "wgsgeog", "e": str(easting), "n": str(northing)},
    )
    lat = find_value(converted, ("wgsLat", "latitude", "lat", "LAT", "y"))
    lon = find_value(converted, ("wgsLong", "longitude", "lon", "lng", "LON", "x"))
    if lat is None or lon is None:
        raise ValueError("坐标转换未返回经纬度。")
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


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise SystemExit("请先安装依赖：python -m pip install -r requirements.txt") from exc

    st.set_page_config(page_title="RecycleMatch HK", page_icon="♻️", layout="wide")
    st.title("♻️ RecycleMatch HK")
    st.caption("香港公共回收点附近推荐 · 决策辅助原型")
    st.info("距离为直线距离；点开步行路线后由 Google Maps 规划实际路线。数据来自项目内冻结的清洗版 CSV。")

    @st.cache_data
    def cached_points() -> pd.DataFrame:
        return load_points()

    try:
        points = cached_points()
    except Exception as exc:
        st.error(f"无法读取项目数据：{exc}。请保持 python_app 与 data 文件夹位于原项目目录中。")
        return

    all_materials = sorted({part.strip() for value in points["waste_type"] for part in value.split(",") if part.strip()})
    with st.sidebar:
        st.header("查找设置")
        mode = st.radio("推荐方式", ["最近的单个回收点", "尽量少跑几个点"], help="少跑几个点使用贪心覆盖启发式，结果是近似方案。")
        selected = st.multiselect("要回收的物料", all_materials)
        ranges = {"不限范围": None, "500 米": 0.5, "1 公里": 1.0, "3 公里": 3.0}
        range_label = st.selectbox(
            "直线搜索范围", list(ranges),
            help="以当前经纬度为中心，只在所选直线距离内搜索回收点。",
        )
        fewer_stops = mode == "尽量少跑几个点" and bool(selected)
        limit = st.slider(
            "最多显示结果", 5, 30, 10, disabled=fewer_stops,
            help="多点方案会显示全部建议停靠点。",
        )

    st.subheader("1. 设置你的位置")
    st.session_state.setdefault("origin_latitude", 22.284)
    st.session_state.setdefault("origin_longitude", 114.137)
    address = st.text_input("搜索香港地址或地标", placeholder="例如：香港大学站")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("搜索地址并定位", type="primary", disabled=not address.strip()):
            try:
                lat, lon, label = geocode_address(address.strip())
                if not (22.0 <= lat <= 22.7 and 113.7 <= lon <= 114.6):
                    raise ValueError("地址坐标超出目前支持的香港范围。")
                st.session_state["origin_latitude"] = lat
                st.session_state["origin_longitude"] = lon
                st.success(f"找到：{label}（{lat:.6f}, {lon:.6f}）")
            except Exception as exc:
                st.error(f"地址定位失败：{exc}")
    with col_b:
        st.caption("地址搜索需要联网。也可以直接在下方输入经纬度。")

    coord1, coord2 = st.columns(2)
    with coord1:
        user_lat = st.number_input("纬度 Latitude", min_value=22.0, max_value=22.7, key="origin_latitude", format="%.6f")
    with coord2:
        user_lon = st.number_input("经度 Longitude", min_value=113.7, max_value=114.6, key="origin_longitude", format="%.6f")
    st.caption("当前原型使用地址搜索或手动坐标；浏览器实时 GPS 可作为后续增强。")

    st.subheader("2. 查看推荐")
    ranked = rank_points(points, user_lat, user_lon, ranges[range_label])
    st.caption(f"搜索范围：{range_label} · 候选回收点：{len(ranked):,}")
    missing: list[str] = []
    if selected:
        available = {item for value in ranked["waste_type"] for item in material_keys(value)}
        covered = [item for item in selected if item.casefold() in available]
        missing = [item for item in selected if item.casefold() not in available]
        st.write(f"范围内物料覆盖：**{len(covered)}/{len(selected)}** · " + ("、".join(covered) or "无"))
        if missing:
            st.warning("范围内未覆盖：" + "、".join(missing) + "。可扩大搜索范围或调整物料。")
    else:
        st.caption("选择物料后可查看覆盖情况。")

    results = fewer_stop_plan(ranked, selected) if fewer_stops else single_stop_plan(ranked, selected)
    if ranked.empty:
        st.info("搜索范围内没有回收点。可扩大搜索范围。")
    elif results.empty:
        if fewer_stops:
            st.info("搜索范围内没有点位接收所选物料。")
        elif not missing:
            st.warning("范围内没有单个点能接收全部所选物料。可切换到「尽量少跑几个点」。")
        else:
            st.info("范围内没有单个点能接收全部所选物料。")
    else:
        if fewer_stops:
            st.write(f"建议停靠 **{len(results)}** 个点。")
        displayed = results if fewer_stops else results.head(limit)
        for rank, row in displayed.iterrows():
            title = row.get("address_en") or row.get("address_tc") or f"回收点 {row.get('cp_id', '')}"
            district = str(row.get("district_id", "")).replace("_", " ")
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"**{rank + 1}. {title}**")
                    st.write(f"{district} · {row.get('legend', '公共回收点')} · {row['distance_km']:.2f} km 直线距离")
                    if selected:
                        accepted = material_keys(row["waste_type"])
                        matches = [item for item in selected if item.casefold() in accepted]
                        st.write("**本点可接收的已选物料** · " + "、".join(matches))
                    st.write("接收物料：" + (row.get("waste_type") or "未注明"))
                    if row.get("accessibilty_notes"):
                        st.caption(str(row["accessibilty_notes"]))
                with right:
                    st.link_button("步行路线 ↗", google_maps_walk_url(user_lat, user_lon, float(row["lat"]), float(row["lgt"])), use_container_width=True)
    st.divider()
    st.caption(f"数据记录：{len(points):,} 个含坐标的回收点。推荐根据静态公开数据计算，不代表实时开放状态。")


if __name__ == "__main__":
    main()
