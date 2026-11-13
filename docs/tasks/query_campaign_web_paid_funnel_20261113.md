# 四个官网 campaign 访问及付费漏斗

- **需求编号**: T115
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-11-13
- **定稿 SQL**: `sql/reports/query_campaign_web_paid_events_20261113.sql`、`sql/reports/query_campaign_web_paid_orders_20261113.sql`
- **执行与汇总**: `scripts/query_campaign_web_paid.py`、`scripts/summarize_campaign_web_paid.py`
- **汇总证据**: `output/campaign_web_paid/summary.json`（本地忽略目录）

## 初始需求

统计 homepage、message_2611_sale、pricing_activity_modal、ad_banner_2026_1111 官网链接访问量，区分新用户/登录用户，并统计后续付费点击、成功付费总数及 Pro/Max 年月套餐。

## 口径

- 北京时间 `[2026-10-28 00:00:00, 2026-11-13 00:00:00)`，UTC `[2026-10-27 16:00:00, 2026-11-12 16:00:00)`；访问、点击和订单均截至 11 月 12 日。
- 网页 PV 为 official_page_view 原始事件行；全量保留匿名访客，不以设备表圈流量。
- 用户已确认按未登录/已登录拆分，仅聊天汇总。`ex_int_arg1>0` 为该次访问已登录，其余未登录；不把未登录解释成新注册。
- 官网范围为生产域名 `immersivetranslate.com` 全路径，排除测试域名7条及 worker域名1条。PV 为原始上报次数，未做无证据的重复上报剔除。
- UV 用 `ex_char_arg3` 浏览器指纹；31,423条官网访问均有非空指纹。各 campaign、各登录状态存在重叠；全窗合计单独去重，不加日UV。
- 购买按钮 `pricing_purchase_btn_click.trigger` 是当前 URL 的 campaign，套餐从 `ex_char_arg2` 获取；该事件的 `campaign` 多为插件已有归因，不能当本次网页campaign使用。
- 点击含试用购买入口；点击依赖插件桥接上报，对纯浏览器访客可能漏记。只报次数，不混用指纹与账号冒充统一人数。
- 订单按 P013 finished 且实付>0 或兑换码；排除软删除；套餐与升级/续费分开核对。
- 付款归因采用 `subscriptionordersource.utmcampaign` → `checkoutsessiontableid=checkout.id` → `checkoutsessionid=order.checkoutsessionid`。来源按会话取最后一条（时间、id唯一决胜）；实测各会话均仅1条。
- checkout 与订单创建时间均在统计期内；不按同账号后续任意订单归因，也不对点击漏报者补造点击。这里不用点击时间关联订单，因此P042点击下界宽限不适用。
- 订单包含升级和续费，不等于新增订阅；未形成完整可比漏斗，不能用这几个不同覆盖的阶段直接计算转化率。
- 业务副本水位：订单北京时间11-13 01:03:58，checkout 01:03:47，来源01:05:32，均越过截止点。
- 只读查询 immdata；不执行写库操作。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|---|---|---|
| 四 campaign 访问 PV/UV | events SQL + summary.json | ✅ |
| 未登录/登录 | 访问时账号ID；用户明确选择此口径 | ✅ |
| 后续购买点击及套餐 | 目标trigger + click_plan；记录点击次数 | ✅ |
| 成功付费及 Pro/Max 年月 | orders SQL；来源精确匹配 | ✅ |
| 北京时间含 11-12 全天 | UTC 半开边界；副本水位核对 | ✅ |

## 结果

| campaign | 未登录PV | 已登录PV | 总PV | 指纹UV | 点击次数 | 付费单/人 |
|---|---:|---:|---:|---:|---:|---:|
| homepage | 240 | 246 | 486 | 361 | 31 | 7 |
| message_2611_sale | 80 | 601 | 681 | 546 | 25 | 5 |
| pricing_activity_modal | 11,227 | 12,810 | 24,037 | 17,097 | 1,423 | 113 |
| ad_banner_2026_1111 | 2,628 | 3,591 | 6,219 | 4,406 | 593 | 41 |
| 合计（UV全窗去重） | 14,175 | 17,248 | 31,423 | 21,558 | 2,072 | 166 |

点击套餐（Pro月/Pro年/Max月/Max年）=89/1552/11/420；付费套餐=52/102/3/9。
成功付费166单对应166个不同账号，无跨campaign付费账号重叠；129笔normal、32笔subscription、5笔upgrade。另有479笔试用、1笔退款，未计入166笔付费。
具体campaign套餐明细与登录状态UV见同次快照的summary.json。

## 连接与复现

DB_agent/.env 未填密码，使用用户指定的另一个仓库 imm_data_dashboard/.env 现有配置；凭据不复制、不打印。脚本对DSN组件做URL编码，且执行前沿用db.assert_readonly拦截写操作。
先运行两个SQL保存events.json/orders.json，再运行summarize_campaign_web_paid.py，禁止混用不同次快照的子集倒减已交付数字。
访问仅使用网页事件，不借设备表限定访问分母，移动端匿名访问也保留；本次补查设备映射仅用于覆盖诊断，最终PV/UV/订单汇总不依赖设备表映射。

## 抽样复核

通过：20笔订单的来源、账号、套餐、时间及实付状态20/20一致；18个不同访客指纹的46条访问/28个campaign×登录状态分组与窄查询一致。无账号错配、重复订单、套餐未分类或finished checkout漏关联订单。所有套餐加总与总量一致；点击/订单范围差异已披露，不报告虚假转化率。抽样结果不作为交付文件保留。
