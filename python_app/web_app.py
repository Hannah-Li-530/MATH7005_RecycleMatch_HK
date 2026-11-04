"""Serve the RecycleMatch HK interface and recommendation API on localhost."""

from __future__ import annotations

import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import webbrowser

import pandas as pd

from app import (
    fewer_stop_plan, google_maps_walk_url, load_points, material_keys,
    rank_points, request_json, single_stop_plan,
)

WEB_DIR = Path(__file__).resolve().parent / "web"
RVM_FILE = WEB_DIR.parent.parent / "data" / "epd_rvm_locations_snapshot.json"
SEARCH_URL = "https://www.map.gov.hk/gs/api/v1.0.0/locationSearch"
CONVERT_URL = "https://www.geodetic.gov.hk/transform/v2/"


@lru_cache(maxsize=1)
def dataset():
    points = load_points().fillna("")
    materials = {
        part.strip().casefold(): part.strip()
        for value in points["waste_type"]
        for part in value.split(",")
        if part.strip()
    }
    return points, materials


@lru_cache(maxsize=1)
def rvm_dataset():
    snapshot = json.loads(RVM_FILE.read_text(encoding="utf-8"))
    return pd.DataFrame(snapshot["machines"]), {
        "retrieved_on": snapshot["retrieved_on"],
        "latest_record_update": snapshot["latest_record_update"],
    }


def rvm_recommendations(lat: float, lon: float, radius: float | None) -> dict:
    machines, metadata = rvm_dataset()
    ranked = rank_points(machines, lat, lon, radius)
    cards = []
    for row in ranked.head(10).to_dict("records"):
        cards.append({
            "name": row["name"],
            "address": row["address"],
            "district": row["district"],
            "opening_hours": row["opening_hours"],
            "contact": row["contact"],
            "updated_at": row["updated_at"],
            "type": "入樽機先導計劃",
            "distance": round(float(row["distance_km"]), 3),
            "matched": ["合資格塑膠飲品樽"],
            "walking_url": google_maps_walk_url(lat, lon, float(row["lat"]), float(row["lgt"])),
        })
    return {
        "cards": cards, "match_count": len(ranked),
        "distance": cards[0]["distance"] if cards else None,
        **metadata,
    }


def recommendations(payload: dict) -> dict:
    lat, lon = float(payload["lat"]), float(payload["lon"])
    if not (22.0 <= lat <= 22.7 and 113.7 <= lon <= 114.6):
        raise ValueError("请输入香港范围内的经纬度。")
    radius = payload.get("radius")
    if radius not in (None, 0.5, 1, 3):
        raise ValueError("请选择有效的搜索范围。")
    mode = payload["mode"]
    if mode == "rvm":
        return rvm_recommendations(lat, lon, radius)
    if mode not in ("one", "few"):
        raise ValueError("请选择有效的推荐方式。")
    points, materials = dataset()
    items = payload["materials"]
    if not isinstance(items, list) or not items or len(items) > len(materials):
        raise ValueError("请至少选择一种回收物品。")
    selected = list(dict.fromkeys(materials[item.strip().casefold()] for item in items))
    ranked = rank_points(points, lat, lon, radius)
    available = {item for value in ranked["waste_type"] for item in material_keys(value)}
    missing = [item for item in selected if item.casefold() not in available]
    result = single_stop_plan(ranked, selected) if mode == "one" else fewer_stop_plan(ranked, selected)

    cards = []
    displayed = result.head(10) if mode == "one" else result
    for row in displayed.to_dict("records"):
        accepted = material_keys(row["waste_type"])
        cards.append({
            "address": row["address_tc"] or row["address_en"] or "地址未提供",
            "district": row["district_id"].replace("_", " "),
            "type": row["legend"],
            "opening_hours": row.get("openhour_tc") or row.get("openhour_en") or "",
            "distance": round(float(row["distance_km"]), 3),
            "matched": [item for item in selected if item.casefold() in accepted],
            "walking_url": google_maps_walk_url(lat, lon, float(row["lat"]), float(row["lgt"])),
        })
    distance = None
    if cards:
        distance = cards[0]["distance"] if mode == "one" else cards[-1]["distance"]
    return {
        "cards": cards, "candidate_count": len(ranked), "match_count": len(result),
        "missing": missing, "coverage": len(selected) - len(missing), "distance": distance,
    }


class Handler(BaseHTTPRequestHandler):
    def send_data(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, value, status: int = 200) -> None:
        self.send_data(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/CHANGELOG.md":
            changelog = WEB_DIR.parent.parent / "CHANGELOG.md"
            self.send_data(changelog.read_bytes(), "text/plain; charset=utf-8")
            return
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript")}
        if url.path in files:
            name, mime = files[url.path]
            self.send_data((WEB_DIR / name).read_bytes(), mime + "; charset=utf-8")
            return
        if url.path == "/api/catalog":
            points, materials = dataset()
            machines, rvm_meta = rvm_dataset()
            self.send_json({
                "count": len(points), "materials": sorted(materials.values()),
                "rvm": {"count": len(machines), **rvm_meta},
            })
            return
        params = parse_qs(url.query)
        if url.path == "/api/places":
            query = params.get("q", [""])[0].strip()
            if not 2 <= len(query) <= 120:
                self.send_json({"error": "请输入 2 到 120 个字符的地点名称。"}, 400)
                return
            try:
                raw = request_json(SEARCH_URL, {"q": query})
                places = raw if isinstance(raw, list) else (
                    raw.get("results") or raw.get("data") or raw.get("suggestions") or []
                )
                self.send_json([
                    {
                        "name": place.get("nameZH") or place.get("nameEN") or query,
                        "district": place.get("districtZH") or place.get("districtEN") or "",
                        "address": place.get("addressZH") or place.get("addressEN") or "",
                        "x": place["x"], "y": place["y"],
                    }
                    for place in places[:8]
                    if isinstance(place, dict) and place.get("x") is not None and place.get("y") is not None
                ])
            except (OSError, ValueError, TypeError, AttributeError):
                self.send_json({"error": "地点搜索暂不可用，可手动输入经纬度。"}, 502)
            return
        if url.path == "/api/coordinates":
            try:
                x, y = float(params["x"][0]), float(params["y"][0])
                if not (780000 <= x <= 900000 and 770000 <= y <= 880000):
                    raise ValueError
            except (KeyError, IndexError, ValueError):
                self.send_json({"error": "所选地点缺少有效坐标。"}, 400)
                return
            try:
                value = request_json(CONVERT_URL, {
                    "inSys": "hkgrid", "outSys": "wgsgeog", "e": str(x), "n": str(y),
                })
                lat, lon = float(value["wgsLat"]), float(value["wgsLong"])
                if not (22.0 <= lat <= 22.7 and 113.7 <= lon <= 114.6):
                    raise ValueError
                self.send_json({"lat": lat, "lon": lon})
            except (OSError, ValueError, KeyError, TypeError):
                self.send_json({"error": "坐标转换暂不可用，可手动输入经纬度。"}, 502)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/recommend":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("请求大小无效。")
            payload = json.loads(self.rfile.read(length))
            result = recommendations(payload)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "请检查地点和所选物料。"
            self.send_json({"error": message}, 400)
            return
        self.send_json(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    dataset()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        raise SystemExit(f"Port {args.port} is already in use. Close the previous window and try again.")
    with server:
        url = f"http://localhost:{args.port}"
        print(f"RecycleMatch HK is running at {url}", flush=True)
        if args.open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
