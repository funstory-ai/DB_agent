# 小米浏览器用户可识别性核查

- **需求编号**: T114
- **规范大类**: query
- **状态**: 进行中
- **日期**: 2026-11-13
- **定稿 SQL**: `sql/reports/query_mi_browser_identifiability_20261113.sql`

## 初始需求

> 「小米浏览器一个推荐的是我们的插件，我们的数据库可以分出来小米浏览器的用户吗？」

即：判断 `immdata` 里能否把「来自/使用小米浏览器的用户」单独识别出来，以及能识别到什么粒度（浏览器使用 vs 推荐来源）。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **行为探查**：北京日 2026-11-12 单日（UTC `2026-11-11 16:00:00` ≤ `created_ts` < `2026-11-12 16:00:00`）；**补充趋势**：北京日 2026-10-14 ~ 2026-11-12 共 30 天（UTC `2026-10-13 16:00:00` ≤ `created_ts` < `2026-11-12 16:00:00`）。**设备/归因档案**：`imt_deviceinfo.createtime` / `imt_campaigninfo.createtime` 在 2026-08-13 ~ 2026-11-13 近 90 天，另跑全表兜底。北京日 = `created_ts + 8h`，SQL 用 UTC 常量边界保分区裁剪，不在时间列上套函数。 |
| 分母 / 分子 | 分母 = 时间窗内活跃 `device_id` 去重数（或档案表设备数）；分子 = 命中「小米浏览器」标识的设备数。本任务是**可识别性核查**，重点是字段取值分布与命中量级，不是某个业务转化率。 |
| 主体 | `device_id`（行为）/ `deviceid`（档案表）；结论须区分「使用小米浏览器的设备」与「由小米浏览器推荐带来的新装」两种完全不同的口径。 |
| 判别维度 | ① `user_behaviour.browser_name` / `browser_version`；② `imt_deviceinfo.browser` / `browseruseragent`；③ `imt_campaigninfo.browser` / `browseruseragent` / `utmsource` / `utmcampaign` / `reference` / `ext*`；④ `user_behaviour.install_from` / `campaign`。 |
| 只读 | 全链路 SELECT；不代跑任何写仓语句。 |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 库内是否有浏览器维度字段，取值有哪些 | `user_behaviour.browser_name` / `imt_deviceinfo.browser` / `browseruseragent` / `imt_campaigninfo.browser`；取值分布已拉 | ✅ |
| 能否命中「小米浏览器」 | 唯一取值 **`browser_name='Miui'`**（UA `XiaoMi/MiuiBrowser/<ver>`）；近 30 天全事件扫描无其它变体 | ✅ |
| 规模与趋势 | 11-12 北京日 1,439 台 / 15,657 事件；11-11 起台阶式放量 | ✅ |
| 能否区分「用小米浏览器」与「小米推荐来源新装」 | **不能**：无专属 UTM/campaign/installchannel；已逐字段证伪 | ✅ |
| 缺口与可用替代口径 | UA 误解析 5.3%、P037 移动端档案缺口、推荐效果近似口径 | ✅ |
| 定稿 SQL | `sql/reports/query_mi_browser_identifiability_20261113.sql`（Q1~Q6） | ✅ |

## 结论

**能分「正在使用小米浏览器的设备」，不能直接分「被小米浏览器推荐位带来的新用户」。**

1. **可识别**：埋点 `user_behaviour.browser_name = 'Miui'` 是小米浏览器在库内的唯一标识，UA 原文为 `XiaoMi/MiuiBrowser/20.x`（安卓 / X11 Linux 两形态）。近 30 天（10-14~11-12）全事件扫描，browser_name 里无 `Xiaomi` / `Mi Browser` 等其它变体。档案表可用 `imt_deviceinfo.browser='Miui'` 或 `browseruseragent LIKE '%MiuiBrowser%'`。
2. **规模（11-12 北京日，明细表）**：1,439 台设备、15,657 条事件；`is_new_user_today='1'` 的 640 台（44.5%）；`real_geo` CN 1,287 台（89.4%），HK 71、US 39、SG 34。`install_from` 几乎全是 `edge_store`（Android 778 / Linux desktop 633），`campaign='none'`。
3. **趋势（日汇总 translate_page，`device_count` 按 event/os/platform/browser 分行求和）**：11-01~11-10 日均约 125 台/日；11-11 = 261（新设备 177）、11-12 = 455（新设备 339），约 3.6 倍台阶；Android 端 40 → 157 → 311 最陡，Linux desktop 73 → 104 → 144。**时间上与「推荐上线」吻合，但库内没有推荐位标记，不能据此断言因果（P043）**，需业务侧给出准确上线日再做前后窗对照。
4. **不能分「推荐来源」的证据**：`imt_deviceinfo.installchannel` 全表 16 个取值无任何小米相关（Miui 设备 96% 标 `edge_store`）；`imt_campaigninfo` 中 `browser='Miui'` 的 1,567 行 `utmsource`/`utmcampaign`/`reference` 全空（仅 1 条无关跳板）；含 `xiaomi` 字样的归因值实为 `via_xiaoming`（人名）与用户翻译的小米研报 PDF 文件名，与渠道无关。即小米浏览器推荐把用户导向 Edge 插件商店，安装链路未透传来源参数。
5. **两处缺口**：
   - **误解析约 5.3%**：`imt_campaigninfo` 里 UA 明确含 `XiaoMi/MiuiBrowser` 的 1,656 行中，88 行被解析成 `Chrome`、1 行 `Edge-chromium`（多带 `swan-mibrowser` 后缀）。行为表不存 UA 原文，**行为层无法补捞**；档案表可用 UA 模糊匹配补。
   - **P037 移动端档案缺口**：行为表 11-12 单日就 1,439 台，`imt_deviceinfo` 全表 `Miui` 仅 346 台。要关联账号/付费须走 P016 双路径（`deviceid` + `ex_int_arg1`），且必然大面积漏，不能只用设备表当全集。
6. **若业务要精确衡量推荐效果**：需在推荐落地链接加专属 UTM（如 `utm_source=xiaomi_browser`）并在扩展安装时透传；当前只能以「首次出现 `browser_name='Miui'` 且 `is_new_user_today='1'` 落在上线日后」近似，并用上线前基线做增量对照。

## 抽样复核（正式交付）

P019 通过。三条独立交叉核对：① 明细层 11-12 北京日（UTC 11-11 16:00~11-12 16:00）`browser_name='Miui'` 去重 1,439 台，与日汇总 `translate_page` 同日 455 台不矛盾（后者仅单事件且按 os 分行，是子集）；② UA 样例 8 条均含 `XiaoMi/MiuiBrowser/20.x`，`browser='Miui'`，`installchannel='edge_store'`，确认 `Miui` 不是同名误标；③ 明细层按 `install_from`/`campaign` 分组的首行 `edge_store`+`none` 占绝对多数，与档案表 `installchannel` 全表分布一致，排除「另有小米专属渠道被聚合掩盖」。量级判断：小米浏览器绝对量小（占全端日活不足 1%）但 11-11 起 3.6 倍跳升且新设备占比 44.5%，不像串组或假零；地区集中 CN 亦符合小米用户分布。异常值说明：汇总表 `device_count` 是维度行之和，不可当跨天去重人数，已在正文与 SQL 注释中标注。
