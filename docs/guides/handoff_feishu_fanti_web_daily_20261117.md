# 飞书表「谷歌_繁体_网页翻译」自动更新 —— 取数交接文档

> 交接日期：2026-11-17　｜　数据来源：Databend `immdata`　｜　交付物：`sql/reports/feishu_fanti_web_daily_full_sql_20261117.sql`
> 适用对象：负责飞书自动更新的项目/同事。文档自包含，**取数 SQL 已实跑验证，写入飞书的部分由接收方实现**。

---

## 1. 这张表是什么

飞书表「谷歌_繁体_网页翻译」是 **Google Ads 一个 campaign 的逐日投放 + 转化漏斗日报**，不是多渠道汇总，也不是我方自己算的表。

| 项 | 值 |
|---|---|
| 广告账户 customer_id | `6036515162` |
| campaign_id | `21597353947` |
| campaign 名称 | 网页翻译_繁体_目标安装_20240816 |
| 广告类型 | SEARCH / MAXIMIZE_CONVERSIONS（来自 `google_ads_campaign_snapshot`） |
| 落地页 UTM（唯一） | `googlekeywords_website_translate_download` |
| 表粒度 | 1 行 = 1 个北京自然日，共 16 列（日期 + 15 数值） |

⚠️ 繁体/简体在 UTM 名字里区分不出来，**必须用 `campaign_id = 21597353947` 过滤**，不能按 UTM 猜。该 campaign 落地页 91 行 URL 100% 只带上面那一个 UTM，点击/消费与 campaign 日报完全相等。

⚠️ Google 后台自报的 `conversions`（126~200/天）**不是**这张表的「安装」或「付费」，它是 Google 自归因、混了页面浏览/下载，`conversion_value` 也不是收入。**禁止用它替换任何列。**

---

## 2. 16 列来源与算法（逐列）

前 7 列来自 Google Ads 日报 + 我方埋点，后 9 列来自用户提供的后端漏斗 SQL（已翻译为 Databend 版）。

| # | 飞书列名 | 输出别名 | 来源表 / 算法 |
|---|---|---|---|
| 1 | 日期 | `report_date` | `google_ads_campaign_daily.report_date`（账户时区 Asia/Shanghai 自然日） |
| 2 | 消费 | `cost_cny` | `sum(cost_micros)/1e6`，人民币原值 |
| 3 | 展现 | `impressions` | `sum(impressions)` |
| 4 | 点击 | `clicks` | `sum(clicks)` |
| 5 | 平均点击价格 | `cpc_cny` | 消费 ÷ 点击，`round(...,2)` |
| 6 | 安装 | `install` | `imt_campaigninfo` 该 UTM 北京日 `count(DISTINCT deviceid)` |
| 7 | 单用户获客成本 | `cpa_cny` | 消费 ÷ 安装，`round(...,2)` |
| 8 | translated | `translated` | 该批设备里 `translated=1` 的去重数 |
| 9 | registered | `registered` | 设备经 `imt_deviceinfo.userid` 桥接 user，`datediff(day, c.createtime, u.createtime) BETWEEN 0 AND 100` 的新建 userid 去重 |
| 10 | clickTry | `clickTry` | 该 user 的 `imt_checkoutsession` userid 去重（窗口 0~100 天） |
| 11 | tryPro | `tryPro` | session 的 `subscriptiongoodssnap.EnableTrial=true` 且订单 `subscriptiontype∈(yearly,monthly)`、`amountpaid=0`、窗口内，订单 id 去重 |
| 12 | paid | `paid` | `orderstatus='finished'` 且 monthly/yearly 系、`amountpaid>0`、窗口内，订单 id 去重 |
| 13 | pro月费订单数 | `pro_monthly` | `subscriptiontype ∈ (monthly, onetime_dogpay_monthly)` |
| 14 | max月费订单数 | `max_monthly` | `subscriptiontype ∈ (max_monthly, onetime_dogpay_max_monthly)` |
| 15 | pro年费订单数 | `pro_yearly` | `subscriptiontype ∈ (yearly, onetime_yearly, onetime_dogpay_yearly)` |
| 16 | max年费订单数 | `max_yearly` | `subscriptiontype ∈ (max_yearly, onetime_dogpay_max_yearly, onetime_max_yearly)` |

**漏斗 JOIN 链**（第 9~16 列）：
```
imt_campaigninfo c  -- 该 UTM 的安装设备（队列基准，北京日分组）
  LEFT JOIN imt_deviceinfo  d ON c.deviceid = d.deviceid      -- 设备→userid
  LEFT JOIN imt_userinfo    u ON d.userid  = u.id             -- 注册时间
  LEFT JOIN imt_checkoutsession s ON u.id = s.userid          -- 点击试用/结算会话
  LEFT JOIN imt_subscriptiongoodsorder o ON s.userid = o.userid -- 订单
```
全部用 `count(DISTINCT ...)`，JOIN 行膨胀不影响计数；`#12 paid == #13+#14+#15+#16` 已验证 24/24 天成立；`#14 max月费`、`#16 max年费` 24 天全为 0（当前无数据，保留列）。

---

## 3. SQL 文件与运行方式

**唯一交付 SQL**：`sql/reports/feishu_fanti_web_daily_full_sql_20261117.sql`
— 一条查询直接输出全部 16 列，24 行（示例窗 2026-10-23~11-15），2026-11-17 实跑通过。

依赖的库表（均只读，无需建表）：
- `immdata.google_ads_campaign_daily`（Google Ads 每日同步写入，03:40 回刷近 7 天）
- `immdata.imt_campaigninfo` / `imt_deviceinfo` / `imt_userinfo` / `imt_checkoutsession` / `imt_subscriptiongoodsorder`

另有「分列排查版」备查：`sql/reports/query_feishu_fanti_web_daily_20261117.sql`（Q1~Q6，含逐列校验查询 Q2/Q3/Q4），交接时可一并给，但**自动更新只需上面那一个 full_sql 文件**。

---

## 4. 时间口径（最容易错的地方）

- 北京自然日 D = UTC `(D-1) 16:00 ~ D 16:00`。
- 广告侧 `report_date` 已是 Asia/Shanghai，直接等值用。
- **我方表禁止在 WHERE 里写 `to_date(date_add(hour,8,createtime))`** —— 百亿级表会全表扫被 kill。SQL 里 WHERE 只放 UTC 粗窗保分区裁剪，北京日只放在 SELECT 投影里，这是硬约定。
- 每次改窗口要**同时改三处**（示例窗 2026-10-23~11-15）：
  1. `ads`：`report_date BETWEEN '2026-10-23' AND '2026-11-15'`
  2. `funnel` 内层 UTC：`c.createtime >= '2026-10-22 16:00:00' AND c.createtime < '2026-11-15 16:00:00'`
  3. `funnel` 外层：`event_datetime BETWEEN to_date('2026-10-23') AND to_date('2026-11-15')`

设目标北京日区间 `[D1, D2]`，则 UTC 粗窗 = `D1-1 16:00:00 ~ D2+1 16:00:00`（左闭右开）。

---

## 5. 写入飞书的约定

1. **按日期覆盖（UPSERT/MERGE 语义）**：Google 每天 03:40 回刷近 7 天，历史天的消费/点击/CPC/CPA 会变；只 append 当天行会导致飞书与库内越差越远。用 `report_date` 做匹配键覆盖同日期行。
2. **建议窗口 T-8 ~ T-1**：覆盖 Google 7 天回刷窗，也能自愈业务表 T-1 延迟。
3. **数值精度**：仅消费 / CPC / CPA 保留 2 位小数，其余为整数。
4. **缺数处理**：若某天 ads 有数据但 funnel 全 NULL（埋点未到），**跳过该行或留空，不要写 0**——0 会被当成真实转化数。
5. **运行时序**：Google 同步 03:40 完成 ⇒ 本任务建议 04:10 之后跑。

---

## 6. 历史行与飞书旧快照的差异（已解释，不是 bug）

把 SQL 当前值与用户提供的飞书 24 天静态快照逐列比对：

| 列 | 吻合天数 / 24 | 列 | 吻合天数 / 24 |
|---|---|---|---|
| 安装 | 24 | paid | 16 |
| max月费 | 24 | clickTry | 13 |
| max年费 | 24 | registered | 10 |
| tryPro | 20 | translated | 5 |
| pro月费 | 19 | | |
| pro年费 | 18 | | |

- **所有差异方向都是「库内 ≥ 飞书」，无一负值**。这是 100 天滚动窗口 + `translated` 回填标志的快照时点效应：飞书每行只算到它被导出的那天，早期安装日（10-23~11-08）之后陆续有注册/试用/付费进入窗口，所以库内当前值更大；越靠近快照日越一致（11-09~11-11 连续 3 天 10 列全等）。
- 已用 `fuse_snapshot` 把业务表回退到 11-16 19:00 重跑，吻合度仅小幅上升（translated 5→7、registered 10→12），证明飞书各行不是同一时刻快照，**无法用单一时间点完全复原**。
- ⇒ **结论**：自动更新统一取库内 T 时点当前值即可，口径自洽；历史行缓慢爬升、与飞书旧快照有差异属正常，不要回调或修正。

---

## 7. 交接后仍需接收方确认的事项（数据侧不阻塞）

取数已 100% 就绪，但写入飞书还缺以下信息（属飞书项目侧）：

| # | 事项 | 说明 |
|---|---|---|
| 1 | 表格类型 | 电子表格 or 多维表格，决定调哪个飞书 API |
| 2 | 表格定位 | 链接或 token、目标 sheet/子表名、日期列位置、起始行 |
| 3 | 写入凭证 | 飞书自建应用 `app_id / app_secret`，且应用需加为该表协作者（群机器人 webhook 不能写单元格） |
| 4 | 范围 | 只这一张「谷歌_繁体_网页翻译」，还是工作簿里其它渠道页也一起（其它页口径未提供） |
| 5 | 回刷覆盖天数 | 默认近 8 天（T-8~T-1），可调整 |

---

## 8. 边界声明

- 本次交接**只覆盖 Google Ads 这一张表的取数**。其它渠道花费、跨渠道归因、ROAS、Superset 看板均不在范围内（用户已明确暂不进计划）。
- 全部产物为只读 SELECT + 文档，**未写库、未建表/结果表/中间表/映射表、未改 ODS 表、未改同步脚本、未接飞书、未建定时任务**。
