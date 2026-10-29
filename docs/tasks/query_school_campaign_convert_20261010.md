# 校园 campaign 两链转化（先核表）

- **需求编号**: T063
- **规范大类**: query
- **状态**: ⏸ **搁置**（2026-10-10：指纹→新装断链，感觉链路有问题）
- **日期**: 2026-10-10
- **定稿 SQL**: （待验收后写入 `sql/reports/`）

## 初始需求

1. 免费/试用未付费/退订：`?via=schooltw&utm_campaign=school_01_free`
2. 即将到期月费：`?via=school&utm_campaign=school_02_month`

先检查 `imt_campaigninfo` 是否漏记；与 `user_behaviour.campaign` 互证；再看转化。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | behaviour 首次出现起：`2026-09-10`～`2026-10-11`（右开） |
| 分母 | 窗内 `user_behaviour.campaign ∈ {school_01_free, school_02_month}` 的设备（及可映射账号） |
| 新装/激活 | P034：`init_page_daily` / `translate_page` + `is_new_user_today='1'`（触链后同窗） |
| 试用/付费 | P013；订单 `createtime >=` 该设备首次带 campaign 时间 |
| 交付 | 对话汇总（样本极小） |

## 官网指纹 → 新装 device_id 链路（2026-10-10 补核）

`official_page_view` 身份字段：

| 字段 | 含义 |
|------|------|
| `ex_char_arg3` | 浏览器指纹 hash |
| `ex_char_arg8` | `fingerprint` / `device_id` / `first_party` |
| `ex_char_arg9` | 与 arg8 对应的身份值 |
| `device_id` | 仅当已装插件且能注入时有值 |

本题官网 PV：`school_01_free` 约 7 个纯指纹访客 + 3 个 first_party；`school_02_month` 1 个纯指纹。

**链路问题（断在第二跳）**：

1. 指纹字段**只出现在官网事件**（`official_page_view` / `official_download_extension_click` 等）。
2. 插件事件（含 `init_page_daily`）**不带** `ex_char_arg3`/`ex_char_arg8`（抽 1 日 init 459 万行：with_arg3=0）。
3. 因此 **无法**用指纹 join 到后续新装 `device_id`；纯指纹访客点下载后，插件侧新 device 与网页指纹无共同键。
4. 本题纯指纹访客后续同指纹事件仍停在官网（下载点击等）；几乎无人变成带 device 的 PV；**新装=0**。

结论：设计意图的「指纹认人 → 再匹配新装设备」在现网埋点上**接不上**；之前用 device_id 分母会漏掉未装插件的官网点击，用指纹也追不到装后转化。

## 表可信度（互证）

| 源 | school_01_free | school_02_month | 结论 |
|----|---------------:|---------------:|------|
| `imt_campaigninfo.utmcampaign` | **0** | **0** | **不准 / 漏记**（本题两链完全没有） |
| `imt_deviceinfo.utmcampaign` | 0 | 2（`utmsource=via_school`） | 严重不全 |
| `imt_subscriptionordersource` | 0 | 0 | 无 |
| `user_behaviour.campaign` | 12 设备 | 4 设备 | **相对最全**，作本题分母 |
| behaviour ∩ campaigninfo | 0/12 | 0/4 | campaign 表相对 behaviour **全漏** |
| behaviour ∩ deviceinfo | 0/12 | 1/4 | deviceinfo 也漏 |

补充：`school_01_free` 的 **带 campaign 行几乎全是 `official_page_view`**（官网落点）；同设备后续插件事件多数**不再带**该 campaign。`via` 在 deviceinfo 里偶发落成 `utmsource=via_school` / `utmcampaign=via_schooltw`，与 `utm_campaign` 字段不一致。

## 转化结果（behaviour 分母，触链后）

| 指标 | school_01_free | school_02_month |
|------|---------------:|---------------:|
| 设备（分母） | 12～13 | 4～5 |
| 可映射 userid | 12 | 4 |
| 新装（P034） | **0** | **0** |
| 新激活（P034） | **0** | **1** |
| 触链后有 init / translate | 11 / 11 | 3 / 4 |
| 试用 | **0** | **0** |
| 现金付费 | **0** | **0** |
| 付费类型 | — | — |

解读：量级极小；人群偏已有插件用户点官网链（非新装投放）。**未见试用/付费转化。** 若邮件点击未把 UTM 写入插件 `campaign`，真实触达会大于库内分母——当前只能答「带得上这两个 campaign 的人」。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 核 `imt_campaigninfo` 准不准 | 上表：本题两链 0 行，相对 behaviour 全漏 | ✅ |
| 与 behaviour.campaign 互证 | 上表 | ✅ |
| 两链转化（新装/激活/试用/付费/类型） | 上表；付费类型无单 | ✅ 待验收 |
| 指纹→新装 device 链路 | 断在插件侧不带指纹；无法闭合 | ✅ |

## 抽样复核

N 极小；交叉以表间互证代替分层抽样。付费/试用分子为 0，与明细查询空结果一致。通过。
