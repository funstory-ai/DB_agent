# 查询：上月繁体官网（/zh-TW/）点击量与点击人数

- **需求编号**: T123
- **规范大类**: query
- **状态**: ✅ 已验收（2026-11-16，wf 状态机 audited）
- **日期**: 2026-11-16
- **定稿 SQL**: `sql/reports/query_zhtw_official_page_pv_uv_20261116.sql`

## 初始需求

> 新需求：帮我拉一下上个月繁体官网的点击量和点击人数

用户 2026-11-16 通过口径确认（4 选 1）拍板：

| 分歧点 | 用户选择 |
|--------|----------|
| 「繁体官网」范围 | **仅 `/zh-TW/` 页面**（不含 `/zh-HK/`、不按访客界面语言） |
| 「点击量 / 点击人数」 | **官网浏览 PV / UV**（`official_page_view` 次数与去重人数） |
| 「点击人数」去重主体 | **身份 ID 统一去重**（device_id + fingerprint + first_party 按类型配对） |
| 交付形态 | **对话里给两个总数**（不产 Excel） |

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **上个月 = 2026-10 北京自然日**：`created_ts >= '2026-09-30 16:00:00' AND created_ts < '2026-10-31 16:00:00'`（北京日 D = (D-1)16:00~D16:00 UTC） |
| 点击量（分子 A） | `event_name='official_page_view'` 且当前页 URL **路径首段 = `zh-TW`** 的事件行数（PV） |
| 点击人数（分子 B） | 同范围内 `COUNT(DISTINCT concat(ex_char_arg8,'|',ex_char_arg9))`，即身份类型 + 身份值配对去重（UV） |
| 主体 | 官网访客身份 ID（`ex_char_arg8` = `device_id` / `fingerprint` / `first_party` / `fingerprint_fallback`；`ex_char_arg9` 为对应值）；`user_behaviour` 无 `userid` 列，官网访客多数无账号，故不套 P018 的 userid 归人 |
| 数据源 | `immdata.user_behaviour`（唯一可用）。官网埋点明细，`ex_char_arg1` = 当前页完整 URL，`ex_char_arg2` = referrer |
| 排除 | `official_page_view` 之外的事件；URL 首段非 `zh-TW` 的页面（含 `zh-HK`、`zh-Hans`、`text#zh-TW` 锚点、参数里带 `/zh-TW/` 的其它页面） |

### 数据源核查结论（开查前）

- 历史汇总表 `imm_official_pv_click_by_utf8_day`（含 `uv` / `click` 两列）**已不存在**（T066 僵尸表清单，业务日停在 2025-11-13），不能用于 2026-10。
- `information_schema` / `system.tables` 中 `immdata` 无 `official` / `pv_click` 相关表；`webdata` 只有 webapp 系列，无官网页面级点击表。
- 官网点击事件 `official_download_extension_click`（10 月全站 185,050）与 `download_extension_click`（222,017）疑似同一行为两套埋点，且用户已选 PV/UV 口径，本题不涉及。
- 官网访客三类身份**不可互通**（指纹 → device_id 断链，见 T063），故按「类型 + 值」配对去重；实测 `COUNT(DISTINCT ex_char_arg9)` 与配对去重结果一致（身份值空间不重叠）。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 上个月（2026-10 北京自然日） | `created_ts` UTC 常量上下界，不对时间列套函数 | ✅ |
| 繁体官网 = 仅 `/zh-TW/` 页面 | URL 路径首段精确匹配 | ✅ |
| 点击量 = 官网浏览 PV | `COUNT(*)` on `official_page_view` | ✅ |
| 点击人数 = 去重 UV | `COUNT(DISTINCT concat(ex_char_arg8,'|',ex_char_arg9))` | ✅ |
| 对话给两个总数 | 不产 Excel，仅对话汇总 + 定稿 SQL 留档 | ✅ |

## 结果

| 指标 | 2026-10（北京自然日） |
|------|----------------------|
| **点击量（PV）** | **663,793** |
| **点击人数（UV，身份 ID 统一去重）** | **98,246** |

参考对照（非本题口径，仅供理解构成）：
- 仅主站 `immersivetranslate.com`（剔除 onboarding 引导子域 / 测试 / 本地）：508,946 PV / 67,840 UV
- 若含 `/zh-HK/`：约 76.4 万 PV / 11.96 万 UV
- 2026-09 同口径：641,419 PV / 103,520 UV（PV +3.5%、UV −5.1%，量级合理）
- 逐日 UV 加总 139,779 ≠ 98,246，因同一访客跨天回访**不可加总**；98,246 是月内去重人数

## 抽样复核（正式交付）

**P019：通过。** 7 条：

1. **定稿 SQL 原样执行**（从文件读 Q1 原样下发，不重写）：663,793 / 98,246 ✅
2. **独立写法复算**：改用 `regexp_replace` + `split_part` 拆路径首段（不依赖 `regexp_extract`），同为 663,793 / 98,246 ✅ —— 两条独立路径一致
3. **逐日加总**：北京日 2026-10-01 ~ 10-31 共 **31 天**，逐日 PV 加总 = 663,793，与 Q1 完全相等 ✅；边界日首 10-01（24,142）、末 10-31（15,643）均在月内，无越窗
4. **量级/假零判断**：日 PV 15,643 ~ 27,294，无假零、无单日量级跳变；9 月同口径 641,419 / 103,520，环比合理 ✅
5. **身份类型分布加总自洽**：device_id 512,446/54,148 + fingerprint 99,196/27,839 + first_party 52,144/16,257 + fingerprint_fallback 2/2 + NULL 5/0 → PV 加总 663,793 ✅、UV 各类型加总 54,148+27,839+16,257+2 = **98,246** ✅ ⇒ 不同身份类型间无 ID 碰撞，配对去重口径成立
6. **误伤排除**：`LIKE '%/zh-TW/%'` 会命中 685,004 行，其中 **21,211 条**是 `app.immersivetranslate.com/text#ja/zh-TW/...` 等 WebApp 文本翻译 hash 路由（已抽样 8 条 URL 确认，非官网页面）；改用 URL 路径首段精确判定后剔除，且「首段=zh-TW 但不含 `/zh-TW/`」漏判为 0 ✅
7. **NULL 身份**：5 行 `ex_char_arg8` / `ex_char_arg9` 均为空，concat 结果为 NULL 被 `COUNT(DISTINCT)` 忽略，故不计入 UV；占比 0.0008%，已在结论披露 ✅

## 已知边界（结论须带）

- `user_behaviour` 官网访客身份三类（`device_id` / `fingerprint` / `first_party`）**不可互通**（T063 已证指纹→device_id 断链），因此 98,246 是「按身份类型+值配对去重」的人数上限口径；同一个人若跨身份类型访问会被计为多人，库内无法进一步合并（P043：无缺失证据不下结论）。
- 全量口径含 `onboarding.immersivetranslate.com` 的繁体引导页 153,309 PV（23.1%）；若业务上「官网」只指主站，应用 508,946 / 67,840 那一组。
- 旧汇总表 `imm_official_pv_click_by_utf8_day` 已不存在，本结果由埋点明细现算，与历史看板数字不可直接对比（P044）。
