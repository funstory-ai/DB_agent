# `immdata.imt_novicetaskrecord`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_novicetaskrecord` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 2571415 |
| 创建时间 | 2026-10-13 12:12:23.303859 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：待补充
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：待补充（易误用字段、同名异义等）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `taskkey` | `varchar(16382)` | YES |  |  |
| 1 | `deviceid` | `varchar(16382)` | YES |  |  |
| 1 | `taskconfigjson` | `varchar(16382)` | YES |  |  |
| 1 | `extenddatajson` | `varchar(16382)` | YES |  |  |
| 1 | `reqheadersjson` | `varchar(16382)` | YES |  |  |
| 1 | `grantid` | `varchar(16382)` | YES |  |  |
| 1 | `sourcetype` | `varchar(16382)` | YES |  |  |
| 1 | `sourcerecordid` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_novicetaskrecord LIMIT 20;
```
