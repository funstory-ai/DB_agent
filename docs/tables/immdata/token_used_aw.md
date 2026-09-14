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
- **常用过滤**：**必须**时间/用户强过滤
- **关联建议**：先读字段再关联
- **勿想当然**：禁止无过滤聚合；优先用汇总表若存在

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
