# 数据与技术来源（核查日期：2026-10-21）

本文件用于项目报告、演示及答辩中的来源注明。所有网页链接均应在提交前再检查一次，并保留下载日期/版本。

## 1. 核心数据：EPD 回收点

- 数据集：**Recyclable Collection Points Data**（可回收物收集点数据）。
- 发布部门：香港环境保护署（EPD）。
- data.gov.hk 数据集页：<https://data.gov.hk/en-data/dataset/hk-epd-recycteam-waste-less-recyclable-collection-points-data>
- CSV 数据资源页：<https://data.gov.hk/en-data/dataset/hk-epd-recycteam-waste-less-recyclable-collection-points-data/resource/6b90e644-a5e7-42c4-97e0-0962104a8899>
- 原始数据发布日：2026-07-08；data.gov.hk 标记为不定期更新，通常在地点有变更时更新。数据介绍覆盖公众场所的回收箱和收集点，以及纸张、金属、塑料、玻璃瓶等材料类别。
- 项目文件：`data/wasteless260708.csv`（保存的原始版本）；`data/RecycleMatch_HK_public_points_clean.csv`（本项目当前工作版）。
- 项目使用方式：data.gov.hk 的 EPD 数据是核心数据源；当前清洗版保留 5,868 条公众可用记录。数据子集筛选沿用此前处理结果，用户已确认冻结，不再追加清洗。后续报告须引用筛选规则/代码、说明排除记录的理由，并以原始 CSV 作为审计参照。
- 数据范围限制：这是设施/地点清单，不是实时状态流；不能据此推断设施此刻开放、满载或可接收。开门时间等字段可能缺失。

### 补充数据：环保署入樽机先导计划（2026-11-04 获取）

- [DATA.GOV.HK 官方目录](https://data.gov.hk/en-data/dataset/hk-epd-rvmpsteam-reverse-vending-machine-pilot-scheme) · [CSDI 官方数据接口](https://portal.csdi.gov.hk/server/rest/services/common/epd_rcd_1638153978303_23086/MapServer/0)
- `data/epd_rvm_locations_snapshot.json` 保存该次查询返回的 120 条入樽机名录记录，覆盖 18 区。经纬度来自 `LATITUDE`、`LONGITUDE`，开放时间和技术支援电话分别来自 `NSEARCH01_TC`、`NSEARCH02_TC`。查询使用 `where=1=1&outFields=*&returnGeometry=false&f=json`。
- `LASTUPDATE` 是记录更新时间，最新值为 2026-10-20 16:05:40。名录提供公布的开放时间，满载和故障状态未知。独立展示入樽机名录及原公众回收点数据，分析分别使用各自统计口径。
- 电子回赠按环保署入樽机先导计划说明，符合资格的塑胶饮品樽每个 HK$0.10。 [环保署计划说明](https://www.epd.gov.hk/epd/english/environmentinhk/waste/pro_responsibility/index.html)

## 2. 地址/地点搜索：香港地政总署 Location Search API

- data.gov.hk 数据集页：<https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-location-search-api>
- API 文档：<https://portal.csdi.gov.hk/csdi-webpage/apidoc/LocationSearchAPI>
- 当前接口格式：`https://www.map.gov.hk/gs/api/v1.0.0/locationSearch?q={查询词}`
- 用途：把用户输入的香港地址、建筑名称、地点或设施名称转换为候选地点。返回候选项含 HK1980 Grid 的 x/y 坐标；因此不能把 x/y 当作纬度/经度直接使用。多候选时由用户选择具体地点。

## 3. 坐标转换：香港地政总署 Coordinates Transformation API

- data.gov.hk API 资源说明：<https://data.gov.hk/en-data/dataset/hk-landsd-openmap-coordinates-transformation-api/resource/8348cb81-8268-4de7-9cab-f614d535f10a>
- 官方手册：<https://www.geodetic.gov.hk/transform/v2/tformAPI_manual.pdf>
- 接口格式示例：`https://www.geodetic.gov.hk/transform/v2/?inSys=hkgrid&outSys=wgsgeog&e={Easting}&n={Northing}`
- 转换输出为 WGS84 纬度 `wgsLat`、经度 `wgsLong`，供 Haversine 距离计算。注意坐标系统标识必须为 `hkgrid`（不能写成 `hkgird`）。
- 手册提醒转换仅适用于香港范围，不应把结果用于需要测量级精度的位置定位；本项目只用于附近回收点推荐。

## 4. 步行路线：Google Maps URLs

- Google 官方 Maps URLs 文档：<https://developers.google.com/maps/documentation/urls/get-started>
- 用途：推荐卡片的“步行路线”链接带入起点、回收点目的地以及 `travelmode=walking`，在 Google Maps 打开路线。官方 Maps URLs 支持以地点名称、地址或纬经度作为起终点。
- 边界：Google Maps 负责外部路线规划；本项目并未自己实现路网最短路、步行时间或实时交通预测，也不把直线距离包装成行走距离。

## 5. 课程要求

- 文件：`assignment/MATH7005_project_2026.pdf`。
- 课程主题要求用香港政府开放数据构建 Python-powered data product，至少以一个 data.gov.hk 数据集作为主要数据，构建至少部分可运行的原型，并说明方法、报告、代码、演示、AI 使用等。请以该 PDF 原文为准。

## 建议的报告引用写法

> Environmental Protection Department. *Recyclable Collection Points Data*. DATA.GOV.HK, published 8 July 2026, [dataset page](https://data.gov.hk/en-data/dataset/hk-epd-recycteam-waste-less-recyclable-collection-points-data), accessed 21 October 2026.

> Lands Department. *Location Search API*. DATA.GOV.HK / GeoInfo Map API, [dataset page](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-location-search-api), accessed 21 October 2026.

> Geodetic Survey Section, Survey and Mapping Office, Lands Department. *User Manual of Using Coordinates Transformation API (Version 2.0)*, [manual](https://www.geodetic.gov.hk/transform/v2/tformAPI_manual.pdf), accessed 21 October 2026.

> Google. *Get Started with Maps URLs*, [documentation](https://developers.google.com/maps/documentation/urls/get-started), accessed 21 October 2026.
