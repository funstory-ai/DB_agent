# `immdata.token_used_aw`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.token_used_aw` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 1248666029 |
| 创建时间 | 2026-03-16 08:58:20.720898 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：Token 使用明细（体量极大，十亿级+）
- **同步方式**：持续/批写
- **业务含义**：细粒度 token 消耗
- **建议粒度**：明细行
- **常用过滤**：**必须**时间/用户强过滤；北京日 = `date_add(hour,8,timestamp)`，WHERE 里不要对时间套 `to_date(...)`（全表扫被 kill），用粗 UTC `timestamp` 预过滤保分区裁剪，精确切分放 Python
- **关联建议**：与供应商网关逐请求日志对账，必须经 `immdata.routing_ledger` 桥接 —— `网关.request_id = RL.upstreamrequestid → RL.routeattemptid = TU.routeattemptid`（P049）。**不要用 `businessid`**（imt-api 自生成 UUID，与网关 UUID 实测 119,176 条交集 0）。
- **勿想当然**：禁止无过滤聚合；`cachedinputusage` 全为 0（imt-api 硬编码 `CachedInputUsage = 0`，缓存 token 已折进 `inputusage`）；`countername` 才是额度归属（Pro 订阅 `user_subs_ai_token_used_count_v2` / 流量包 `user_ai_package_used_count`）；**"服务" = `productline`，不是 `providername`**（后者是上游供应商）。
- **成本口径**：本表是权威账本，逐条经 `routing_ledger` 验证与上游原始用量 **100% 相等**（T082），不要因汇总差异倒推「我方少记」；汇总前须排除网关侧 `finish_reason='length'` 的 max_tokens 幽灵行（P050）。

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `tenantid` | `bigint` | YES |  |  |
| 1 | `providername` | `varchar(16382)` | YES |  |  |
| 1 | `productline` | `varchar(16382)` | YES |  |  |
| 1 | `categoryname` | `varchar(16382)` | YES |  |  |
| 1 | `resourcename` | `varchar(16382)` | YES |  |  |
| 1 | `actualresourceid` | `varchar(16382)` | YES |  |  |
| 1 | `inputusage` | `bigint` | YES |  |  |
| 1 | `cachedinputusage` | `bigint` | YES |  |  |
| 1 | `outputusage` | `bigint` | YES |  |  |
| 1 | `delta` | `bigint` | YES |  |  |
| 1 | `usageunit` | `varchar(16382)` | YES |  |  |
| 1 | `timestamp` | `timestamp` | YES |  |  |
| 1 | `recordtype` | `varchar(16382)` | YES |  |  |
| 1 | `businessid` | `varchar(16382)` | YES |  |  |
| 1 | `actionid` | `varchar(16382)` | YES |  |  |
| 1 | `countername` | `varchar(16382)` | YES |  |  |
| 1 | `counterperiod` | `varchar(16382)` | YES |  |  |
| 1 | `clientip` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.token_used_aw LIMIT 20;
```
