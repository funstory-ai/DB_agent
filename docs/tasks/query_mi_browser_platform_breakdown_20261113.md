# T114 追问：小米浏览器数据的平台构成

- **需求编号**: T116
- **规范大类**: query
- **状态**: 进行中
- **日期**: 2026-11-13
- **定稿 SQL**: `sql/reports/query_mi_browser_platform_breakdown_20261113.sql`

## 初始需求

> 「这个是只有手机端的数据？另外的是什么平台的」

承接 T114：确认 `browser_name='Miui'` 这批数据是否只有手机端，并解释其中 `Linux / desktop`、`iOS / mobile`、`Android / tablet` 等非手机端记录的真实设备形态；顺带给出「另外那些浏览器」的平台构成以备另一种理解。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **明细主窗**：北京日 2026-11-12 单日，UTC `2026-11-11 16:00:00` ≤ `created_ts` < `2026-11-12 16:00:00`（与 T114 Q2 完全一致，便于对数字）；**趋势**：日汇总 `dates` 2026-09-14 ~ 2026-11-12；**档案表 UA** 全表（仅查 UA 原文与平台字段，不做时间结论）。北京日 = `created_ts + 8h`，SQL 用 UTC 常量边界，不对时间列套函数。 |
| 分母 / 分子 | 分母 = 北京日 11-12 `browser_name='Miui'` 的 `device_id` 去重数（T114 实测 1,439）；分子 = 各 `os_name` × `platform_type` 组合的去重设备数。注意同一设备可能跨组合上报，分组合计可大于分母，须用独立去重核对。 |
| 主体 | `device_id`（行为）/ `deviceid`（档案表）。 |
| 平台判据 | 以埋点 `os_name` + `platform_type` 为一层，以档案表 `browseruseragent` 原文（Mobile / X11 / Android 版本 / 机型 Build 号）为第二层交叉印证；不以 `install_from` 或 `real_geo` 推断设备形态。 |
| 只读 | 全链路 SELECT；不代跑任何写仓语句。 |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| Miui 是否只有手机端，各平台占比 | Q1/Q2，同一次查询出总数与各平台 | ✅ |
| `Linux / desktop` 是什么设备 | Q4 UA 原文 + 版本线 + 档案 platform 字段 | ✅ |
| `iOS / mobile`、`Android / tablet` 是否真实 | Q2/Q4，iOS 为噪声，无 tablet 行 | ✅ |
| 11-11 起突增来自哪个平台 | Q5 按天 × 平台 | ✅ |
| 另一种理解：其它主流浏览器的平台构成 | Q6 | ✅ |
| 结论与定稿 SQL | 本文 + `sql/reports/query_mi_browser_platform_breakdown_20261113.sql` | ✅ |

## 结论

**不是只有手机端。11-12 北京日 1,439 台（有 device_id 的去重设备）拆成三块：**

| 平台 | 设备 | 占比 | 事件 | 新设备 | 说明 |
|------|------|------|------|--------|------|
| `Android / mobile` | 811 | 56.4% | 9,750 | 489 (60.3%) | 真·小米/Redmi 手机，UA 带 `Android 16/17` + 机型 Build 号 + `Mobile Safari` |
| `Linux / desktop` | 639 | 44.4% | 5,897 | 158 (24.7%) | UA 为 `X11; Linux x86_64 ... XiaoMi/MiuiBrowser/20.6.x`，无 Mobile/Android 字样 |
| `iOS / mobile` | 5 | 0.3% | 10 | 4 | UA 是 iPhone + CriOS 却拼了 `XiaoMi/MiuiBrowser/20.32`，判为 UA 伪装/拼接噪声 |

- 分平台相加 1,455 > 1,439：**17 台设备同日在两个 os 下上报**（跨 OS 重合）。
- 另有 **1,785 条事件（11.4%）device_id 为 NULL**，Android 11.7% / Linux 11.0% 分布均匀，不偏斜平台占比；`GROUP BY device_id` 会比 `COUNT(DISTINCT device_id)` 多 1 个 NULL 组（1,440 vs 1,439），T114 的 1,439 口径无需修订。

**`Linux / desktop` 到底是什么（证据边界 P043）**：UA 是标准桌面 Chromium 135 模板 + `XiaoMi/MiuiBrowser/18.9 / 20.6 / 20.8` 版本线；手机端是 `20.32 / 15.4 / 13.16` 另一条版本线；埋点 `os_version='unknown'`，档案表 `platform='Linux'` 804 条 vs `'Android OS'` 762 条（全表累计），`extenddata` 只有 abField/语言、无机型。623 台与 Android 组完全不重合，是独立设备。**能确认的是「桌面形态的小米浏览器 UA」；库内不能判定它是 PC/桌面版小米浏览器，还是安卓平板/手机切桌面 UA 模式**——行为表不存 UA 原文与设备型号，档案表 UA 已被改写成通用 X11 模板。要证实需客户端补上报机型字段或业务侧确认小米浏览器端形态，此处不臆断。

**突增只来自手机端（对用户判断推荐效果最关键）**：日汇总 `translate_page` 11-01~11-10 基线里 **Linux desktop 才是存量主力**（58~129 台/日，Android 仅 22~40）。11-11 起 Android 40 → 157（新 127）→ 311（新 261），Linux 只 73 → 104 → 144（新 50 → 78）。即这波增量几乎全在 Android 手机端，桌面组仅小幅同步上扬。若推荐位在手机端浏览器内，形态吻合；**但库内无推荐位标记，仍不能据此下因果结论（P043）**。

**若「另外的」指其它浏览器（Q6，11-12 translate_page）**：Chrome 主要 Windows 352,779 / macOS 102,713；Microsoft Edge Windows 204,018 / Android 17,742；UC Browser Android 17,184；Safari macOS 16,279 / iOS 11,475；Electron Windows 3,496（桌面客户端）。全端以桌面 Chrome/Edge 为绝对主体，Miui 在 Android 311 + Linux 144。

## 抽样复核（正式交付）

P019 通过。① **P044 一致性**：Q1 在单条 SQL 内同时给出 total=1,439 与 Android 811 / Linux 639 / iOS 5，与 T114 Q2 的 1,439 对齐，不用两次查询相减。② **差 1 解释已证实**：Q3 得 1,423 个单 OS 组 + 17 个双 OS 组 = 1,440，比 1,439 多 1，Q1/H 查到 `device_id IS NULL` 事件 1,785 条，`GROUP BY` 会单列 NULL 组而 `COUNT(DISTINCT)` 不计，两者自洽；Q3 后半确认空 ID 在两平台比例接近，不造成平台占比偏差。③ **UA 交叉印证**：档案表 platform='Linux' 的 6 条样例 UA 全为 `X11; Linux x86_64 ... XiaoMi/MiuiBrowser/20.6.x`，手机组样例含 `MI 6X Build/... Mobile Safari` 机型串，iOS 仅 1 条档案且为 iPhone+CriOS 拼接 UA，与明细层 5 台的量级一致，判为噪声合理。④ 量级合理性：11-12 汇总 translate_page 合计 455 台（Android 311 + Linux 144）小于明细层 1,439 台，符合「汇总仅单事件、明细含全事件」的预期，不是串组或假零。
