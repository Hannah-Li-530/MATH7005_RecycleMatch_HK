"use strict";

const labels = {
  "Metals": "金属", "Paper": "纸张", "Plastics": "塑料", "Food Waste": "厨余",
  "Rechargeable Batteries": "充电池", "Plastic Bottle": "塑料瓶",
  "Glass Bottles": "玻璃瓶", "Fluorescent Lamp": "荧光灯管", "Clothes": "衣物",
  "Computers": "电脑", "Printer Cartridges": "打印机墨盒", "Barbeque Fork": "烧烤叉",
  "Beverage Cartons": "饮品纸盒", "Regulated Electrical Equipment": "受管制电器",
  "Small Electrical and Electronic Equipment": "小型电器",
};
const byId = id => document.getElementById(id);
const label = name => labels[name] || name;
let mode = "one";
let findType = "general";
let catalogData;
let recommendationRequest;
let placeSearchSequence = 0;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败，请稍后重试。");
  return data;
}

async function loadCatalog() {
  try {
    const catalog = await request("/api/catalog");
    catalogData = catalog;
    showCatalogCount();
    const available = new Set(catalog.materials);
    const ordered = [...Object.keys(labels), ...catalog.materials.filter(name => !labels[name])];
    byId("checks").replaceChildren(...ordered.filter(name => available.has(name)).map(name => {
      const tile = element("label", "check");
      const input = element("input");
      input.type = "checkbox";
      input.value = name;
      tile.append(input, element("span", "", label(name)));
      return tile;
    }));
  } catch {
    byId("datasetCount").textContent = "数据暂未载入。请刷新页面后重试。";
  }
}

function showCatalogCount() {
  if (!catalogData) return;
  byId("datasetCount").textContent = findType === "rvm"
    ? "全港 " + catalogData.rvm.count + " 条官方入樽机名录记录"
    : "全港 " + catalogData.count.toLocaleString("zh-HK") + " 条公众可用回收点记录";
}

function showEmpty(message) {
  byId("cards").replaceChildren(element("div", "empty", message));
}

function buildCard(point, index, currentMode) {
  const card = element("article", "card");
  const badges = element("div", "badges");
  const rank = currentMode === "few" ? "回收点 " + (index + 1) : (index === 0 ? "最近匹配" : "可选回收点");
  badges.append(element("span", "badge top", rank));
  if (point.type) badges.append(element("span", "badge", point.type));
  if (point.district) badges.append(element("span", "badge", point.district));
  const left = element("div");
  const items = element("div", "items");
  for (const name of point.matched) items.append(element("span", "chip", label(name)));
  left.append(badges, element("div", "address", point.name || point.address));
  if (point.name) left.append(element("p", "machine-address", point.address));
  left.append(items);
  if (point.contact) {
    const info = element("p", "machine-info", "营运商电话：");
    const phone = element("a", "", point.contact);
    phone.href = "tel:+852" + point.contact.replace(/[^0-9]/g, "");
    info.append(phone);
    left.append(info);
  }

  const right = element("div", "dist", point.distance.toFixed(2) + " km");
  if (point.opening_hours) {
    const hours = element("details", "opening-hours");
    hours.append(element("summary", "", "查看开放时间"), element("div", "", point.opening_hours));
    right.append(hours);
  } else {
    right.append(element("small", "", "开放时间：数据未提供"));
  }
  const link = element("a", "route-link", "步行路线 ↗");
  link.href = point.walking_url;
  link.target = "_blank";
  link.rel = "noopener";
  right.append(link);
  card.append(left, right);
  return card;
}

function setMode(next) {
  mode = next;
  for (const id of ["one", "few"]) {
    byId(id).classList.toggle("on", id === mode);
    byId(id).setAttribute("aria-pressed", String(id === mode));
  }
  render();
}

function setFindType(next) {
  findType = next;
  const isRvm = next === "rvm";
  for (const [id, active] of [["generalTab", !isRvm], ["rvmTab", isRvm]]) {
    byId(id).classList.toggle("on", active);
    byId(id).setAttribute("aria-pressed", String(active));
  }
  byId("materialControls").hidden = isRvm;
  byId("recommendModes").hidden = isRvm;
  byId("rvmSource").hidden = !isRvm;
  byId("controlsTitle").textContent = isRvm ? "设置出发地点" : "设置回收需求";
  byId("resultsTitle").textContent = isRvm ? "附近入樽机" : "推荐回收点";
  byId("search").textContent = isRvm ? "查找附近入樽机 →" : "查找附近回收点 →";
  showCatalogCount();
  render();
}

async function render() {
  recommendationRequest?.abort();
  const controller = new AbortController();
  recommendationRequest = controller;
  const latText = byId("lat").value.trim();
  const lonText = byId("lon").value.trim();
  const selected = Array.from(byId("checks").querySelectorAll("input:checked"), input => input.value);
  const radius = byId("radius").value ? Number(byId("radius").value) : null;
  const currentMode = findType === "rvm" ? "rvm" : mode;
  const isRvm = currentMode === "rvm";
  const note = byId("note");
  const coverLabel = byId("coverLabel");
  coverLabel.textContent = isRvm ? "每个合资格饮品樽电子回赠" : (radius === null ? "物料覆盖" : "范围内物料覆盖");
  byId("stopLabel").textContent = isRvm ? "匹配入樽机" : (mode === "one" ? "匹配回收点" : "建议停靠点");
  byId("distanceLabel").textContent = !isRvm && mode === "few" ? "最远推荐点直线距离" : "最近匹配直线距离";
  note.hidden = !isRvm;
  note.classList.remove("warn");
  if (isRvm) note.textContent = "适用于符合计划条件的塑胶饮品樽。开放时间来自名录，满载和故障状态未知。";
  for (const id of ["nstop", "cover", "maxdist"]) byId(id).textContent = "—";
  if (isRvm) byId("cover").textContent = "HK$0.10";
  if (!latText || !lonText || (!isRvm && !selected.length)) {
    byId("subtitle").textContent = isRvm ? "设置起点后按直线距离查找" : "选择物品和起点后开始搜索";
    showEmpty(isRvm ? "请搜索出发地点、使用定位或手动输入经纬度。" : "请先选择至少一种回收物品，再搜索地点或输入经纬度。");
    return;
  }
  const lat = Number(latText), lon = Number(lonText);
  byId("subtitle").textContent = "正在查找附近回收点…";
  showEmpty("正在计算推荐结果…");
  try {
    const result = await request("/api/recommend", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({lat, lon, radius, mode: currentMode, materials: selected}),
      signal: controller.signal,
    });
    if (controller.signal.aborted) return;
    if (isRvm) {
      const range = radius === null ? "不限范围" : byId("radius").selectedOptions[0].text;
      byId("subtitle").textContent = range + " · 名录获取于 " + result.retrieved_on +
        " · 名录记录最近更新 " + result.latest_record_update.slice(0, 10);
      byId("nstop").textContent = result.match_count;
      byId("maxdist").textContent = result.distance === null ? "—" : result.distance.toFixed(2) + " km";
      if (result.cards.length) {
        byId("cards").replaceChildren(...result.cards.map((point, index) => buildCard(point, index, currentMode)));
      } else {
        showEmpty("当前范围内没有匹配的入樽机，可在高级选项扩大范围。");
      }
      return;
    }
    const count = result.candidate_count.toLocaleString("zh-HK");
    const range = radius === null ? "按距离排序" : byId("radius").selectedOptions[0].text;
    byId("subtitle").textContent = "已选 " + selected.length + " 类物品 · " + range + " · " + count + " 个候选点";
    byId("nstop").textContent = result.match_count;
    byId("cover").textContent = result.coverage + "/" + selected.length;
    byId("maxdist").textContent = result.distance === null ? "—" : result.distance.toFixed(2) + " km";
    note.hidden = false;
    note.classList.toggle("warn", result.missing.length > 0);
    if (result.missing.length) {
      note.textContent = (radius === null ? "清单中未找到：" : "范围内未覆盖：") + result.missing.map(label).join("、") +
        (radius === null ? "。" : "。可以扩大搜索范围。");
    } else if (currentMode === "one") {
      note.textContent = result.cards.length
        ? "每个匹配点均可接收全部已选物料，列表按直线距离排序。"
        : "没有单个回收点能接收全部已选物料，可切换到「尽量少跑点」。";
    } else {
      note.textContent = "以下回收点合计接收全部已选物料。";
    }
    if (result.cards.length) {
      byId("cards").replaceChildren(...result.cards.map((point, index) => buildCard(point, index, currentMode)));
    } else {
      showEmpty(result.candidate_count ? "当前条件下没有匹配的回收点。" : "当前搜索范围内没有公众回收点。");
    }
  } catch (error) {
    if (controller.signal.aborted) return;
    byId("subtitle").textContent = "推荐结果暂不可用";
    showEmpty(error.message || "请稍后重试。");
  }
}

function useCoordinates(lat, lon, message) {
  byId("lat").value = Number(lat).toFixed(6);
  byId("lon").value = Number(lon).toFixed(6);
  byId("placeStatus").textContent = message;
  byId("placeResults").replaceChildren();
  render();
}

async function searchPlace() {
  const query = byId("placeQuery").value.trim();
  const status = byId("placeStatus");
  const results = byId("placeResults");
  const sequence = ++placeSearchSequence;
  results.replaceChildren();
  if (query.length < 2) {
    status.textContent = "请输入至少两个字符的香港地址或地点名称。";
    return;
  }
  status.textContent = "正在搜索地点…";
  try {
    const places = await request("/api/places?" + new URLSearchParams({q: query}));
    if (sequence !== placeSearchSequence) return;
    status.textContent = places.length ? "请选择出发地点。" : "找不到匹配地点，请试试更完整的名称。";
    for (const place of places) {
      const button = element("button", "place-option", [place.name, place.district, place.address].filter(Boolean).join(" · "));
      button.type = "button";
      button.onclick = async () => {
        const selection = ++placeSearchSequence;
        status.textContent = "正在定位所选地点…";
        try {
          const {lat, lon} = await request("/api/coordinates?" + new URLSearchParams({x: place.x, y: place.y}));
          if (selection === placeSearchSequence) useCoordinates(lat, lon, "已选择：" + place.name);
        } catch (error) {
          if (selection === placeSearchSequence) status.textContent = error.message;
        }
      };
      results.append(button);
    }
  } catch (error) {
    if (sequence === placeSearchSequence) status.textContent = error.message;
  }
}

byId("gps").onclick = () => {
  if (!navigator.geolocation) {
    byId("placeStatus").textContent = "当前浏览器不支持定位，可搜索地点或手动输入坐标。";
    return;
  }
  const sequence = ++placeSearchSequence;
  byId("placeStatus").textContent = "正在获取当前位置…";
  navigator.geolocation.getCurrentPosition(
    ({coords}) => {
      if (sequence === placeSearchSequence) useCoordinates(coords.latitude, coords.longitude, "已取得当前位置。");
    },
    () => {
      if (sequence === placeSearchSequence) byId("placeStatus").textContent = "未能获取当前位置，可搜索地点或手动输入坐标。";
    },
    {timeout: 12000, maximumAge: 30000}
  );
};
byId("placeSearch").onclick = searchPlace;
byId("placeQuery").onkeydown = event => { if (event.key === "Enter") searchPlace(); };
byId("search").onclick = render;
byId("generalTab").onclick = () => setFindType("general");
byId("rvmTab").onclick = () => setFindType("rvm");
byId("one").onclick = () => setMode("one");
byId("few").onclick = () => setMode("few");
byId("radius").onchange = render;
byId("checks").onchange = render;
setMode("one");
loadCatalog();
