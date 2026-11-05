"""RecycleMatch HK Python-native course product, v0.7.6.

All project logic and UI declarations are Python. The map is rendered with the
third-party Folium/Leaflet Streamlit component; no project-authored JavaScript,
or Node toolchain is used. Container styling and scroll navigation use
third-party Python APIs; their browser implementation belongs to those packages.
Contribution: AI-assisted implementation. Fill actual primary contributor and
reviewer names for this component in CONTRIBUTIONS.md before submission.
"""
from pathlib import Path
import hashlib
import re
import pandas as pd
import streamlit as st
import st_yled as ui
from streamlit_scroll_to_top import scroll_to_here
import folium
from folium.plugins import BeautifyIcon
from streamlit_folium import st_folium
from core import google_maps_walk_url, material_keys
from recycling_service import (ROOT, LABELS, points, ranked_candidates, query_plan,
                               compare_plans, search_places, place_coordinates)
from reward_schemes import reward_details, GREEN_SOURCE
from rewards_model import RATES, green_estimate, cash_estimate, budget_rewards, load_rewards
from evaluate_recommendations import ORIGINS, BUNDLES

VERSION = "v0.7.6"
NAV = ["尋找回收點", "綠綠賞積分與禮品", "推薦依據與分析"]
RANGES = {"不限範圍": None, "500 米": .5, "1 公里": 1, "3 公里": 3}
GREEN_REDEMPTION_SITES = "https://www.wastereduction.gov.hk/zh-hk/redemption-designated-recycling-stores"
GREEN_APP_GUIDE = "https://www.wastereduction.gov.hk/zh-hk/article/green-mobile-app"


def panel(key=None, *, background="#FFFFFF", padding="24px"):
    """Style native Streamlit containers through a third-party Python API."""
    options = dict(background_color=background, border=True, padding=padding)
    if key is not None:
        options["key"] = key
    return ui.container(**options)


def label(key):
    return LABELS.get(key.casefold(), key)


def names(items):
    return "、".join(label(x) for x in sorted(items))


def go(view, context=None):
    """Navigate while keeping the independent query model in session state."""
    st.session_state["nav"] = view
    if context is not None:
        st.session_state["guide_context"] = context


def clear_materials():
    st.session_state["query"]["materials"] = []
    for key in list(st.session_state):
        if key.startswith("_material_"):
            st.session_state[key] = False


def apply_place_choice():
    """Apply the chosen address immediately; the user need not confirm twice."""
    candidates = st.session_state.get("places", [])
    choice = st.session_state.get("place_choice")
    if choice is None:
        return
    try:
        place = candidates[int(choice)]
        lat, lon = place_coordinates(place)
        st.session_state["query"].update(lat=lat, lon=lon)
        st.session_state["_lat"], st.session_state["_lon"] = lat, lon
        st.session_state["place_label"] = place.get("nameZH") or place.get("nameEN") or "已選地點"
        st.session_state.pop("place_error", None)
    except (IndexError, OSError, ValueError, TypeError, KeyError) as exc:
        st.session_state["place_error"] = f"地點座標轉換失敗：{exc}。可手動輸入座標。"


def update_query_value(widget_key, model_key):
    st.session_state["query"][model_key] = st.session_state[widget_key]
    if model_key in ("lat", "lon"):
        st.session_state["place_label"] = "手動座標"


def query_signature(q, kind=None):
    """Keep map selection tied to the exact query that produced its points."""
    fields = (kind or q.get("kind", "公眾回收"), f"{q['lat']:.6f}", f"{q['lon']:.6f}",
              q.get("radius_label", "不限範圍"), q.get("scope", "全部回收點"),
              q.get("mode", "單點最近"), ",".join(sorted(q.get("materials", []))))
    return "|".join(map(str, fields))


def map_widget_key(signature, focused_rank=None):
    value = signature + "|focus=" + str(focused_rank or "origin")
    return "nearby_map_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def set_map_focus(record, signature):
    """Card action: recenter the map on its matching numbered marker."""
    st.session_state["map_focus"] = {**record, "signature": signature, "source": "card"}
    st.session_state["map_scroll_request"] = signature
    # The map key changes with its focused rank, so the selected-object event
    # remains read-only and an older selection cannot override this card action.


def selected_map_rank(map_state, rows):
    """Resolve a clicked Leaflet marker to the same rank used by result cards."""
    if not map_state:
        return None
    tooltip = map_state.get("last_object_clicked_tooltip") or ""
    match = re.match(r"#(\d+)\b", str(tooltip))
    if match:
        return int(match.group(1))
    clicked = map_state.get("last_object_clicked") or {}
    if isinstance(clicked, dict) and clicked.get("lat") is not None:
        try:
            lat = float(clicked["lat"])
            raw_lon = clicked.get("lng", clicked.get("lon"))
            lon = float(raw_lon)
        except (TypeError, ValueError):
            return None
        if rows:
            nearest = min(rows, key=lambda row: (float(row["lat"]) - lat) ** 2 +
                          (float(row["lgt"]) - lon) ** 2)
            if abs(float(nearest["lat"]) - lat) < .001 and abs(float(nearest["lgt"]) - lon) < .001:
                return int(nearest["result_rank"])
    return None


def init():
    st.session_state.setdefault("query", {"lat": 22.340947, "lon": 114.179515,
                                        "materials": [], "radius_label": "不限範圍",
                                        "scope": "全部回收點", "mode": "單點最近", "kind": "公眾回收"})
    st.session_state.setdefault("nav", NAV[0])
    st.session_state.setdefault("wallet", {"material": None, "quantity": 0.0, "existing": 0.0})


def location_controls(q):
    st.markdown("**我的位置**")
    with st.form("location_search_form", clear_on_submit=False):
        query_col, search_col = st.columns([4, 1])
        with query_col:
            query = st.text_input("搜尋香港地址或地點", key="_place_query", placeholder="例如：大學站", label_visibility="collapsed")
        with search_col:
            submitted = st.form_submit_button("搜尋", use_container_width=True)
    if submitted:
        try:
            with st.spinner("查詢地政總署候選地點…"):
                st.session_state["places"] = search_places(query)
                st.session_state["place_choice"] = None
                st.session_state.pop("place_error", None)
            if not st.session_state["places"]:
                st.warning("找不到候選地點，請嘗試輸入完整名稱或手動座標。")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            st.session_state["place_error"] = f"地點搜尋暫不可用：{exc}。可手動輸入座標。"
    if st.session_state.get("place_error"):
        st.warning(st.session_state["place_error"])
    candidates = st.session_state.get("places", [])
    if candidates:
        st.selectbox("選擇地點（選取後自動套用）", range(len(candidates)),
                              format_func=lambda i: candidates[i].get("nameZH") or candidates[i].get("nameEN") or str(i+1),
                              index=None, key="place_choice", on_change=apply_place_choice)
    st.caption("目前地點：" + st.session_state.get("place_label", "九龍塘示範起點；可更改"))
    with st.expander("手動調整座標", expanded=False):
        a, b = st.columns(2)
        with a:
            st.number_input("緯度", value=q["lat"], min_value=22.0, max_value=22.7, format="%.6f", key="_lat",
                            on_change=update_query_value, args=("_lat", "lat"))
        with b:
            st.number_input("經度", value=q["lon"], min_value=113.7, max_value=114.6, format="%.6f", key="_lon",
                            on_change=update_query_value, args=("_lon", "lon"))
        st.caption("地址搜尋需要網絡；手動座標可離線使用。距離為直線距離。")


def display_map(frame, origin_lat, origin_lon, signature, focus_km=3.0):
    """Render a Leaflet map and link marker clicks with the numbered result list."""
    if frame.empty:
        return
    if st.session_state.get("map_scroll_request") == signature:
        scroll_to_here(400, key="return_to_recommendation_map")
        st.session_state.pop("map_scroll_request", None)
    st.subheader("附近推薦地圖", anchor="recommendation-map")
    focus = st.session_state.get("map_focus", {})
    if focus.get("signature") != signature:
        focus = {}
    widget_key = map_widget_key(signature, focus.get("result_rank", focus.get("number")))
    ordered = frame.copy()
    if "result_rank" not in ordered:
        ordered["result_rank"] = range(1, len(ordered) + 1)
    ordered = ordered.head(10).copy()
    if "address_tc" in ordered:
        ordered["name"] = ordered["address_tc"].fillna("").replace("", "地址未提供")
    elif "name" in ordered:
        ordered["name"] = ordered["name"].fillna("地址未提供")
    else:
        ordered["name"] = ordered.get("address", pd.Series(["地址未提供"] * len(ordered), index=ordered.index)).fillna("地址未提供")
    markers = ordered[ordered["distance_km"] <= focus_km].copy()
    focused_row = None
    if focus:
        same = frame[frame["result_rank"].astype(str).eq(str(focus.get("result_rank")))]
        if not same.empty:
            focused_row = same.iloc[0].to_dict()
        elif focus.get("lat") is not None:
            focused_row = focus
        if focused_row and not markers["result_rank"].astype(str).eq(str(focus.get("result_rank"))).any():
            focused_row["name"] = focused_row.get("address_tc") or focused_row.get("name") or "地址未提供"
            markers = pd.concat([markers, pd.DataFrame([focused_row])], ignore_index=True)
    markers = markers.drop_duplicates(subset="result_rank").sort_values("result_rank")
    if markers.empty:
        st.info(f"起點 {focus_km:g} 公里內沒有推薦點；完整結果仍列於下方。")
        return
    markers["lat"] = markers["lat"].astype(float)
    markers["lgt"] = markers["lgt"].astype(float)
    center_lat = float(focused_row["lat"]) if focused_row else float(origin_lat)
    center_lon = float(focused_row.get("lgt", focused_row.get("lon"))) if focused_row else float(origin_lon)
    zoom = 15 if focused_row else 13
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, control_scale=True,
                   tiles="OpenStreetMap", prefer_canvas=True,
                   scroll_wheel_zoom=False, double_click_zoom=False)
    folium.CircleMarker([origin_lat, origin_lon], radius=9, color="#ffffff", weight=3,
                        fill=True, fill_color="#286a9b", fill_opacity=1,
                        tooltip="起點", popup="目前出發位置").add_to(m)
    for row in markers.to_dict("records"):
        rank = int(row["result_rank"])
        title = row.get("name") or "地址未提供"
        is_selected = focus and str(focus.get("result_rank")) == str(rank)
        icon = BeautifyIcon(
            number=rank, icon_shape="circle", border_width=2,
            border_color="#ffffff", text_color="#ffffff",
            background_color="#286a9b" if is_selected else "#168265")
        popup = f"{rank}. {title} · {float(row['distance_km']):.2f} km"
        folium.Marker([row["lat"], row["lgt"]], icon=icon,
                      tooltip=f"#{rank}｜{title}",
                      popup=folium.Popup(popup, min_width=260, max_width=360)).add_to(m)
    if not focused_row:
        bounds = [[min([origin_lat, *markers["lat"].tolist()]),
                   min([origin_lon, *markers["lgt"].tolist()])],
                  [max([origin_lat, *markers["lat"].tolist()]),
                   max([origin_lon, *markers["lgt"].tolist()])]]
        m.fit_bounds(bounds, padding=(18, 18), max_zoom=15)
    map_state = st_folium(m, height=360, use_container_width=True, key=widget_key,
                          returned_objects=["last_object_clicked", "last_object_clicked_tooltip"])
    rank = selected_map_rank(map_state, markers.to_dict("records"))
    if rank is not None:
        selected_rows = frame[frame["result_rank"].astype(int).eq(rank)]
        if not selected_rows.empty:
            selected = selected_rows.iloc[0].to_dict()
            st.session_state["map_focus"] = {**selected, "result_rank": rank,
                                              "signature": signature, "source": "map"}
            selected_name = selected.get("address_tc") or selected.get("name") or "已選回收點"
            st.info(f"地圖已選第 {rank} 個點：{selected_name} · 距起點 {float(selected['distance_km']):.2f} km")
            st.link_button("查看此點步行路線 ↗", google_maps_walk_url(
                origin_lat, origin_lon, selected["lat"], selected["lgt"]))
    note = f"綠色編號對應下方清單；地圖顯示起點 {focus_km:g} 公里內最多 10 個點。距離為直線距離，實際步行路線以地圖服務為準。"
    if focused_row:
        note = f"地圖已定位第 {focused_row.get('result_rank')} 個推薦點；如與起點較遠，起點標記可能在目前視野外。" + note
    st.caption(note + " 縮放請使用地圖右上／左上角的 ＋／－；滑鼠滾輪用於捲動頁面。")



def public_cards(frame, wanted, q, signature, prefix="public"):
    for number, row in enumerate(frame.to_dict("records"), 1):
        row["result_rank"] = number
        title = row.get("address_tc") or row.get("address_en") or "地址未提供"
        reward = reward_details(row["legend"])
        with panel():
            left, right = st.columns([4, 1])
            with left:
                st.caption(f"{number}. {row['legend']} · {str(row['district_id']).replace('_', ' ')}")
                st.markdown(f"**{title}**")
                st.caption("可回收：" + names(wanted & material_keys(row["waste_type"])))
                if reward["reward_kind"] == "green_points":
                    st.button(":blue[綠綠賞 · 查看積分與禮品 ↗]", key=f"{prefix}_green_{number}",
                              on_click=go, args=(NAV[1], {"name": title, **reward}))
                else:
                    st.caption("綠綠賞待核實；不表示未參加")
            with right:
                st.markdown(f"**{row['distance_km']:.2f} km**")
                st.caption("直線距離")
                st.button("在地圖查看 " + str(number), key=f"{prefix}_map_{number}",
                          on_click=set_map_focus, args=(row, signature))
                st.link_button("步行路線 ↗", google_maps_walk_url(q["lat"], q["lon"], row["lat"], row["lgt"]))
                focus = st.session_state.get("map_focus", {})
                if focus.get("signature") == signature and str(focus.get("result_rank")) == str(number):
                    st.caption("📍 地圖目前定位於此點")
            with st.expander("開放安排與獎勵識別依據"):
                st.write(row.get("openhour_tc") or row.get("openhour_en") or "開放時間：名錄未提供")
                st.write(reward["reward_note"])
                if row["legend"] == "Recycling Spots":
                    st.write("流動點須先確認具體開站日期及本次交收安排。")
                contact = row.get("contact_tc") or row.get("contact_en")
                if contact:
                    st.write("名錄聯絡電話：" + str(contact))


def cash_results(q):
    st.markdown("### 入樽機回贈")
    ranked = ranked_candidates(q["lat"], q["lon"], RANGES[q["radius_label"]], cash=True)
    st.caption(f"120 條官方名錄快照（2026-11-04）· 範圍內 {len(ranked)} 條；與綠綠賞積分分開計算。")
    with panel():
        st.markdown("**回收價值估算**")
        bottles = st.number_input("合資格塑膠飲品樽數量", min_value=0, value=0, step=1, key="bottles")
        amount, count = cash_estimate(bottles)
        st.metric("預計電子回贈", f"HK${amount:.2f}")
        st.caption(f"每樽 HK$0.10，每張八達通或每個 AlipayHK 賬戶每天最多 30 樽；本次按 {count} 樽估算，假設當天尚未領取。以現場及計劃規則為準。")
        st.link_button("官方地圖與狀態 ↗", "https://www.hkrvms3.com.hk/hk/")
    if ranked.empty:
        st.info("目前範圍內沒有入樽機記錄，可擴大範圍。")
    shown = ranked.head(10).copy()
    shown["result_rank"] = range(1, len(shown) + 1)
    signature = query_signature(q, kind="入樽機回贈")
    display_map(shown, q["lat"], q["lon"], signature, RANGES[q["radius_label"]] or 3.0)
    st.markdown("#### 推薦結果")
    for i, row in enumerate(ranked.head(10).to_dict("records"), 1):
        row["result_rank"] = i
        with panel():
            st.subheader(f"{i}. {row['name']}")
            st.write(row["address"])
            st.write(f"距起點 {row['distance_km']:.2f} km · 港幣回贈，非綠綠賞會員積分")
            st.button("在地圖查看 " + str(i), key=f"cash_map_{i}",
                      on_click=set_map_focus, args=(row, signature))
            focus = st.session_state.get("map_focus", {})
            if focus.get("signature") == signature and str(focus.get("result_rank")) == str(i):
                st.caption("📍 地圖目前定位於此點")
            with st.expander("名錄開放時間與聯絡資料"):
                st.write(row.get("opening_hours") or "未提供")
                st.write(row.get("contact") or "聯絡資料未提供")
                st.caption("滿載與故障狀態未接入，不將名錄狀態當作即時可用。")
            st.link_button("步行路線 ↗", google_maps_walk_url(q["lat"], q["lon"], row["lat"], row["lgt"]))


def search_view():
    q = st.session_state["query"]
    kind = st.segmented_control("查找類型", ["公眾回收", "入樽機回贈"], default=q["kind"], required=True,
                                key="_kind", on_change=update_query_value, args=("_kind", "kind"))
    left, right = st.columns([1, 1.8], gap="large")
    with left, panel("query_panel"):
        st.markdown("### 設定回收需求" if kind == "公眾回收" else "### 設定出發位置")
        if kind == "公眾回收":
            st.caption("5,868 條公眾回收點名錄記錄，不等於 5,868 台機器。")
        location_controls(q)
        if kind == "公眾回收":
            material_title, clear_col = st.columns([3, 1])
            material_title.markdown("**我想回收**")
            clear_col.button("一鍵清空", on_click=clear_materials, key="clear_materials", use_container_width=True)
            columns = st.columns(2)
            chosen = []
            available = {item for raw in points().waste_type for item in material_keys(raw)}
            for i, item in enumerate([item for item in LABELS if item in available]):
                with columns[i % 2], st.container(border=True):
                    if st.checkbox(label(item), value=item in q["materials"], key="_material_"+item):
                        chosen.append(item)
            q["materials"] = chosen
            st.caption(f"已選 {len(chosen)} 類；塑膠和塑膠瓶分開匹配。")
        with st.expander("搜尋範圍", expanded=False):
            st.selectbox("直線搜尋範圍", list(RANGES), index=list(RANGES).index(q["radius_label"]), key="_radius",
                         on_change=update_query_value, args=("_radius", "radius_label"))
    with right, panel("results_panel"):
        if kind == "入樽機回贈":
            cash_results(q)
            return
        st.markdown("### 推薦回收點")
        st.info("**想回收，也想賺積分？**　選「只看綠綠賞」尋找已識別的參與設施。", icon="🎁")
        scope_col, mode_col = st.columns([1, 1])
        scope = scope_col.segmented_control("回收點範圍", ["全部回收點", "只看綠綠賞"], default=q["scope"], required=True,
                                             key="_scope", on_change=update_query_value, args=("_scope", "scope"))
        if scope == "只看綠綠賞":
            st.caption("按設施類別識別的 719 條記錄；未核實智能設備不在此子集，不代表未參加。")
        mode = mode_col.segmented_control("推薦方式", ["單點最近", "盡量少跑點"], default=q["mode"], required=True,
                                           key="_mode", on_change=update_query_value, args=("_mode", "mode"))
        if not q["materials"]:
            st.info("先選擇回收物，結果會按當前起點與範圍更新。")
            return
        plan = query_plan(q["lat"], q["lon"], q["materials"], RANGES[q["radius_label"]], scope, q["mode"])
        result = plan["result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("匹配點數／方案停靠數", len(result), border=True)
        c2.metric("實際方案覆蓋", f"{len(plan['covered'])}/{len(q['materials'])}", border=True)
        distance = result.distance_km.iloc[0] if q["mode"] == "單點最近" and len(result) else result.distance_km.max()
        c3.metric("最近點／方案最遠點", f"{distance:.2f} km" if len(result) else "—", border=True)
        if plan["missing"]:
            st.warning("範圍內未覆蓋：" + names(plan["missing"]))
        if result.empty:
            st.warning("沒有單一回收點接收全部所選物料；可嘗試盡量少跑點或擴大範圍。" if q["mode"] == "單點最近" else "沒有可覆蓋所選物料的點。")
        st.caption("按直線距離排序；「盡量少跑點」優先增加物料覆蓋，不保證最短路線。")
        st.button("比較推薦方法 →", on_click=go, args=(NAV[2],), key="compare_current")
        shown = result.head(10) if q["mode"] == "單點最近" else result
        signature = query_signature(q)
        shown = shown.copy()
        shown["result_rank"] = range(1, len(shown) + 1)
        display_map(shown, q["lat"], q["lon"], signature, RANGES[q["radius_label"]] or 3.0)
        st.markdown("#### 推薦結果")
        public_cards(shown, set(q["materials"]), q, signature)


def wallet_update(key, field):
    st.session_state["wallet"][field] = st.session_state[key]


def gift_cards(gifts, locked, total):
    if not gifts:
        st.caption("當前類別沒有此類獎勵。")
        return
    cols = st.columns(3)
    source = load_rewards()["source"]
    for i, gift in enumerate(gifts):
        with cols[i % 3], panel():
            category = {"daily": "日常禮品", "voucher": "禮券", "digital": "平台積分"}[gift["category"]]
            st.caption(category + (" · 下次目標" if locked else " · 預計已達門檻"))
            st.subheader(gift["name"])
            st.metric("所需積分", f"{gift['points']:,} 分")
            if locked:
                st.caption(f":gray[還差 {gift['gap']:,.2f} 分]")
            else:
                st.success(f"預計達到門檻；換 1 份後剩 {gift['after']:,.2f} 分")
            with st.expander("換領方式與限制"):
                st.write(gift["detail"])
                st.link_button("官方說明 ↗", gift.get("source", source))


def rewards_view():
    st.button("← 返回回收推薦", on_click=go, args=(NAV[0],), key="return_search")
    st.header("綠綠賞 · 積分與禮品")
    context = st.session_state.get("guide_context")
    if context:
        st.info(context["name"])
    st.caption("按官方快照估算。參與積分回收，不表示該處也提供實體禮品換領。未連接會員賬戶或即時庫存。")
    wallet = st.session_state["wallet"]
    with panel():
        st.subheader("我的積分預算")
        a, b, c = st.columns([1.5, 1, 1])
        with a:
            options = list(RATES)
            material = st.selectbox("這次回收什麼", options, index=options.index(wallet["material"]) if wallet["material"] else None,
                                    placeholder="請選擇要估算的回收物", key="_wallet_material",
                                    on_change=wallet_update, args=("_wallet_material", "material"))
        with b:
            piece = material and RATES[material][1] == "piece"
            quantity = st.number_input("數量（件）" if piece else "重量（公斤）", min_value=0.0, value=float(wallet["quantity"]),
                                       step=1.0 if piece else .1, disabled=material is None, key="_wallet_quantity",
                                       on_change=wallet_update, args=("_wallet_quantity", "quantity"))
        with c:
            existing = st.number_input("已有積分（選填）", min_value=0.0, value=float(wallet["existing"]), step=1.0,
                                       key="_wallet_existing", on_change=wallet_update, args=("_wallet_existing", "existing"))
        try:
            earned = green_estimate(material, quantity)
            total, _, _ = budget_rewards(existing, earned)
        except ValueError as exc:
            st.error(str(exc))
            return
        a, b, c = st.columns(3)
        a.metric("本次預計積分", f"{earned:,.2f} 分")
        b.metric("已有積分", f"{existing:,.2f} 分")
        c.metric("預計合計", f"{total:,.2f} 分")
        with st.expander("計分規則與來源"):
            st.write("重量類至少 0.1 公斤；件數須為整數。10 分／公斤組包括紙張、金屬、其他塑膠、小型電器、節能燈泡／光管、充電池和紙包飲品盒。具體品種及現場計分以計劃為準。")
            if context:
                st.write(context["reward_note"])
            st.link_button("官方綠綠賞說明 ↗", GREEN_SOURCE)
    st.subheader("選擇想換的獎勵")
    a, b = st.columns(2)
    category = a.selectbox("獎勵類別", ["all", "daily", "voucher", "digital"],
                           format_func=lambda x: {"all":"全部獎勵", "daily":"日常禮品", "voucher":"禮券", "digital":"平台積分"}[x])
    descending = b.selectbox("已達門檻獎勵排序", ["積分從高到低", "積分從低到高"]) == "積分從高到低"
    total, ready, future = budget_rewards(existing, earned, category=category, descending=descending)
    st.caption("每項按單獨換 1 份計算，不代表能同時兌換全部禮品；達到積分門檻不保證庫存、賬戶資格或剩餘額度。")
    section = st.radio("瀏覽獎勵", ["已達積分門檻", "下次想換"], horizontal=True, key="reward_section")
    if section == "已達積分門檻":
        st.write(f"預計已達門檻：{len(ready)} 項")
        gift_cards(ready, False, total)
    else:
        st.write(f"繼續攢分的目標：{len(future)} 項")
        gift_cards(future, True, total)
    st.caption("獎勵參考核對日期：2026-11-05，非即時禮品名錄。")
    st.subheader("官方換領資料")
    source_cols = st.columns(3)
    source_cols[0].link_button("完整官方禮品兌換表 ↗", load_rewards()["source"], use_container_width=True)
    source_cols[1].link_button("18 個實體換領點 ↗", GREEN_REDEMPTION_SITES, use_container_width=True)
    source_cols[2].link_button("兌換及 App 使用說明 ↗", GREEN_APP_GUIDE, use_container_width=True)
    st.caption("參考版本：日常禮品表 2026-05；期間限定禮券表 2026-07；名單核對日期 2026-11-05。禮品數量有限，換完即止；本頁不提供即時庫存。其他公眾回收點或入樽機的綠綠賞資格須另行確認。")
    st.button("↑ 返回回收推薦", on_click=go, args=(NAV[0],), key="bottom_return")


def mining_view():
    st.subheader("物料共收：哪些組合更難一站收齊？")
    points_data = points()
    bundles = [{"物料組合": names(bundle), "名錄共同接收記錄": sum(set(bundle) <= material_keys(raw) for raw in points_data.waste_type)} for bundle in BUNDLES]
    st.dataframe(pd.DataFrame(bundles), hide_index=True)
    st.caption("每條名錄記錄是一條事務；共現不意味著某個未知點必定接收後項。查詢仍逐條精確匹配。")
    st.subheader("參數敏感性：規則數量不等於發現數量")
    sensitivity = pd.read_csv(Path(__file__).parent / "output/apriori_sensitivity.csv")
    st.dataframe(sensitivity.rename(columns={"min_support":"最小支持度", "min_confidence":"最小置信度",
                                            "frequent_itemsets":"頻繁項集", "rules":"規則數", "short_positive_rules":"短前項且 lift > 1"}), hide_index=True)
    st.caption("同一數據，支持度 1%／2%／5%，置信度 60%／80%／90%；主要結果仍採用 2% 和 60%。")
    st.info("5,868 條記錄只有 60 種不同物料組合。1% 與 2% 支持度下頻繁項集數相同；提高到 5% 後為 1,024。規則很多，主要反映設施名錄的共收結構。")
    with st.expander("設施類別是否影響共收規律？", expanded=True):
        profile = pd.read_csv(Path(__file__).parent / "output/rule_facility_profile.csv")
        selected = st.selectbox("檢查規則", list(profile.rule.unique()))
        st.dataframe(profile[profile.rule.eq(selected)].drop(columns="rule"), hide_index=True)
        weighting = pd.read_csv(Path(__file__).parent / "output/rule_pattern_weighting.csv")
        st.dataframe(weighting[weighting.rule.eq(selected)].drop(columns="rule"), hide_index=True)
        st.caption("同物料模式重複出現會影響總體規則。按模式各計一次僅是重新加權診斷，分母不再是設施數，不能解釋為站點機率。零分母顯示為空，不填成零置信度；某類前項樣本極少時，即使置信度或提升度很高也不能概括。")


def comparison_view():
    q = st.session_state["query"]
    st.subheader("少跑幾站，是否值得去更遠？")
    use_current = st.radio("對照來源", ["當前查詢", "60 個固定案例"], horizontal=True, key="comparison_source")
    if use_current == "當前查詢":
        if not q["materials"]:
            st.info("請先回到尋找頁選擇物料，或選擇固定案例。")
            return
        lat, lon, radius, materials, scope = q["lat"], q["lon"], RANGES[q["radius_label"]], q["materials"], q["scope"]
        origin = "當前查詢"
    else:
        cases = [(name, lat, lon, radius, bundle) for name, lat, lon in ORIGINS for radius in (.5, 1, 3) for bundle in BUNDLES]
        i = st.selectbox("選擇固定案例", range(len(cases)), key="fixed_case", format_func=lambda i:f"{cases[i][0]} · {cases[i][3]} km · {names(cases[i][4])}")
        origin, lat, lon, radius, materials = cases[i]
        scope = "全部回收點"
    st.info(f"{origin}（{lat:.6f}, {lon:.6f}）· {radius if radius is not None else '不限'} km · {names(materials)} · {scope}")
    table, plans = compare_plans(lat, lon, materials, radius, scope)
    st.dataframe(table, hide_index=True)
    columns = st.columns(3)
    context = dict(lat=lat, lon=lon)
    for col, (method, frame) in zip(columns, plans.items()):
        with col:
            st.write("**"+method+"**")
            if frame.empty:
                st.caption("該方法未返回方案。")
            for row in frame.to_dict("records"):
                with panel():
                    st.write(row.get("address_tc") or row.get("address_en"))
                    st.write(f"距同一起點 {row['distance_km']:.2f} km")
                    st.caption("匹配："+names(set(materials) & material_keys(row["waste_type"])))
                    st.link_button("步行路線 ↗", google_maps_walk_url(lat, lon, row["lat"], row["lgt"]))
    st.caption("最遠站點距起點不是總步行路程。0 站表示沒有方案。貪心不保證全局最少站數或最短路線。")
    with st.expander("固定案例總體證據"):
        st.write("60 個案例＝5 個起點 × 4 個組合 × 3 個半徑。兩種多點方法都完整覆蓋的 57 個案例中，貪心在 18 個減少停靠數；全部 60 個中有 3 個最遠站點更遠。")
        st.caption("當前案例中貪心與可得物料最少停靠窮舉對照一致，不構成普遍最優證明。")
        st.download_button("下載 180 行完整對照結果", (ROOT/"analysis_waste/recommendation_results.csv").read_bytes(), "recommendation_results.csv", "text/csv")


def analysis_view():
    st.button("← 返回回收推薦", on_click=go, args=(NAV[0],), key="analysis_return")
    st.header("推薦依據與分析")
    section = st.radio("分析任務", ["物料共收與穩健性", "推薦方法對照", "區級補充分析"], horizontal=True, key="analysis_section")
    if section == "物料共收與穩健性":
        mining_view()
    elif section == "推薦方法對照":
        comparison_view()
    else:
        st.subheader("回收點與廢物處置量：相對供給對照")
        st.image(str(ROOT / "analysis_waste/district_scatter.png"))
        district = pd.read_csv(ROOT / "analysis_waste/district_results.csv")
        district_names = {
            "Central_Western":"中西區", "Eastern":"東區", "Southern":"南區", "Wan_Chai":"灣仔區",
            "Kowloon_City":"九龍城區", "Kwun_Tong":"觀塘區", "Sham_Shui_Po":"深水埗區", "Wong_Tai_Sin":"黃大仙區",
            "Yau_Tsim_Mong":"油尖旺區", "Islands":"離島區", "Kwai_Tsing":"葵青區", "North":"北區",
            "Sai_Kung":"西貢區", "Sha_Tin":"沙田區", "Tai_Po":"大埔區", "Tsuen_Wan":"荃灣區", "Tuen_Mun":"屯門區",
        }
        district["district_id"] = district["district_id"].map(district_names).fillna(district["district_id"])
        district = district.rename(columns={
            "district_id":"地區", "domestic_tpd":"家居垃圾（噸／日）", "commercial_industrial_tpd":"工商業垃圾（噸／日）",
            "msw_tpd":"都市固體廢物（噸／日）", "point_count":"公眾回收點數", "points_per_1000_tpd":"每千噸垃圾對應點數",
        })
        st.dataframe(district, hide_index=True, use_container_width=True)
        st.caption("17 個可比地區，2024 年堆填處置量對 2026 年 7 月點位快照；不是垃圾產生量、容量或因果分析。離島口徑不一致，未硬拼成 18 區。Spearman rho = 0.505。")


def main():
    st.set_page_config(page_title="RecycleMatch HK · Python", page_icon="♻", layout="wide")
    ui.init()
    init()
    brand, version = st.columns([4, 1])
    brand.markdown("### ♻ :green[RecycleMatch] HK")
    with version:
        st.caption(VERSION + " · Python 提交版")
        with st.popover("版本與更新"):
            st.write("v0.7.6：淺灰綠頁面、白色卡片與藍色積分區；清單按鈕返回原地圖並定位同號標記。")
            st.caption("地址搜尋、手動座標、物料一鍵清空、兩種推薦、綠綠賞估算與禮品、入樽機回贈及課程分析均保留。")
    st.header("回收，可以更順路。")
    st.caption("選擇回收物和出發位置，查看附近公眾回收點；藍色綠綠賞入口可開啟積分與禮品。")
    st.segmented_control("頁面", NAV, key="nav", required=True, label_visibility="collapsed")
    if st.session_state["nav"] == NAV[0]:
        search_view()
    elif st.session_state["nav"] == NAV[1]:
        rewards_view()
    else:
        analysis_view()
    st.divider()
    st.caption("數據來源：data.gov.hk 環保署公眾回收點（2026-07 凍結快照）。名錄不是即時可用狀態；未知獎勵資格不代表未參加。地圖與路線需要聯網，數值推薦和分析可在本地使用。")


if __name__ == "__main__":
    main()
