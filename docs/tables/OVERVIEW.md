# immdata 库总览（沉浸式翻译插件）

本项目**只使用** `immdata`。其它 schema 默认忽略。

## 分层（按命名习惯，便于选表）

| 层级/前缀 | 含义 | 使用建议 |
|-----------|------|----------|
| `user_behaviour` / `user_access_log` | 插件埋点明细 | 必须限时间+事件；优先用汇总/DWD |
| `imt_*` | 业务库同步（账号/设备/订单/归因） | 注意 `isdeleted`；ID 字段命名不统一 |
| `dwd_*` | 明细清洗层 | 订单分析优先 `dwd_order_clean` |
| `dws_*` | 汇总层 | 如用户首单 `dws_order_user_firsts` |
| `ads_*` | 应用/报表层 | 现成指标快照 |
| `imm_*` / `user_*_day` | 主题汇总、画像、日指标 | 看表文档粒度与类型 |
| `vw_*` / `imm_view_*` | 视图 | 先确认定义再引用 |
| `tmp_*` / `t_*` / `temp*` / `test*` | 临时/一次性分析 | **默认不当正式口径** |

## 核心实体与常见键

| 概念 | 常见字段 | 注意 |
|------|----------|------|
| 注册用户 | `imt_userinfo.id`，别处常写 `userid` / `user_id` | 另有 `uid`，勿与 `id` 混用未核对 |
| 设备 | 埋点 `device_id`；业务表 `deviceid` | 格式是否一致需抽样 |
| 订单 | `imt_subscriptiongoodsorder.id`；清洗表 `order_id` | 付费用 `dwd_order_clean.is_paid_order` |
| 结账会话 | `checkoutsessionid` / 表内 `id` | `created` 会话≠付费 |

## 转化类指标口径（P018，已确认）

- **转化主体**：有账号归 **userid**（同一账号多设备只算 1 人）；没有账号用 **device_id**
- 行为次数描述：用户下多设备 **累加**
- 单设备多账户：多为羊毛党；付费分子走订单 userid，behaviour 不进付费分子。同一 `deviceid`、同一 `installtime`、多个 userid 时，去重必须有唯一决胜键；这台是否付过费看任一账号（P018-E）
- **移动端（P037）**：android/ios/ipados 埋点 `device_id` 大部分不在 `imt_deviceinfo`；涉及移动端须说明，勿把设备表当移动端全集

## 查数选表捷径

- **活跃/翻译行为**：`user_behaviour`（必限时、不对时间套函数）；账号并表用 **deviceinfo + `ex_int_arg1` 双路径（P016）**；或日汇总 `user_translate_*`（注意类型）
- **按语言拆分**：设备母语用 `imm_device_native_language`（target 优先 + interface fallback；上游 `imm_user_target_lan_stats`）。账号级：userid 下按语言 **SUM(cnt)**，取最大者为母语（P020）
- **付费/会员/试用**：`imt_subscriptiongoodsorder`（`amountpaid` 口径）；**不要用** `dwd_order_clean` / `dws_order_user_firsts`（P012 过程表）
- **账号/设备档案**：`imt_userinfo`、`imt_deviceinfo`（join 前对 userid+deviceid 去重，P015）
- **归因**：`imt_subscriptionordersource`、`imt_campaigninfo`
- **团队租户用量看板**：`imt_teamusagedaily` + `imt_teamtenant`（日用量须 `SUM(usage)`，见 task4）
- **Google Workspace 按日看板**：读 `imm_workspace_daily_kpi` / `imm_workspace_daily_dim`（**勿**挂 90d 直查 `user_behaviour`，P022；ETL 见 task5）
- **付费墙按日看板**：读 `imm_paywall_daily_kpi` / `imm_paywall_daily_wide_*`（**勿用** `ads_ab_paywall_*`、~~`imm_paywall_daily_dim`~~；ETL 见 task6）
- **按天累计类看板选型**：先实测直查耗时；慢则日汇总中间表 + 北京日增量 TASK（样板：`imm_user_target_lan_stats` / Workspace 日表，P022）

## 维护

- 结构同步：`python scripts/sync_table_catalog.py`（仅 immdata）
- 索引：[`INDEX.md`](INDEX.md)
- 单表：[`immdata/`](immdata/)
