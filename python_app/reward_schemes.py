"""Reward labels based on the official scheme scope and inventory categories.

The public-point CSV has no per-point reward enrollment field. GREEN$ labels
therefore identify the published facility category, not a live enrollment check.
Smart bins, private shops and general public bins stay unverified.
"""

GREEN_TYPES = {"Recycling Stations/Recycling Stores", "Recycling Spots"}
GREEN_SOURCE = "https://www.wastereduction.gov.hk/zh-hk/recycling-faq/green-electronic-participation-incentive-scheme-faq"


def reward_details(facility_type: str, *, rvm_pilot: bool = False) -> dict:
    if rvm_pilot:
        return {
            "reward_kind": "cash_rebate",
            "reward_label": "港幣回贈 · 入樽機先導計劃",
            "reward_note": "合資格塑膠飲品樽可領取八達通／AlipayHK電子回贈，按計劃規則及機器確認結算。",
            "reward_source": "https://www.hkrvms3.com.hk/hk/faq.htm",
        }
    if facility_type in GREEN_TYPES:
        return {
            "reward_kind": "green_points",
            "reward_label": "綠綠賞積分 · 按設施類別識別",
            "reward_note": "依據官方計劃適用範圍及本條名錄的「綠在區區」設施類別識別，並非逐點現場核驗。服務時段內請出示App當前會員二維碼或已登記積分卡；具體物料計分及入賬以現場為準。",
            "reward_source": GREEN_SOURCE,
        }
    note = "這條名錄沒有提供逐點綠綠賞參與資料；待核實不表示未參加，出發前可向營運方確認。"
    if facility_type == "Smart Bin":
        note = "官方綠綠賞包含環保署運作或指定的智能回收設施。這條名錄沒有逐臺參與字段，當前尚未與官方指定設備清單對應；待核實不表示未參加。"
    elif facility_type == "Street Corner Recycling Shops":
        note = "回收店可能按物料收購，價格和收購安排請向店方確認；名錄未說明綠綠賞資格。"
    return {
        "reward_kind": "unverified",
        "reward_label": "綠綠賞待核實",
        "reward_note": note,
        "reward_source": GREEN_SOURCE,
    }
