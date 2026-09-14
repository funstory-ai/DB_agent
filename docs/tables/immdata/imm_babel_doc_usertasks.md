# `immdata.imm_babel_doc_usertasks`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_babel_doc_usertasks` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 2236402 |
| 创建时间 | 2025-05-07 04:49:19.476645 |
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
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `status` | `varchar(16382)` | YES |  |  |
| 1 | `filename` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `int` | YES |  |  |
| 1 | `taskid` | `varchar(16382)` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `overall_progress` | `varchar(16382)` | YES |  |  |
| 1 | `runcount` | `varchar(16382)` | YES |  |  |
| 1 | `recordid` | `varchar(16382)` | YES |  |  |
| 1 | `recordtype` | `varchar(16382)` | YES |  |  |
| 1 | `oss_vendor` | `varchar(16382)` | YES |  |  |
| 1 | `taskstatus` | `varchar(16382)` | YES |  |  |
| 1 | `eventdata` | `varchar(16382)` | YES |  |  |
| 1 | `totalpagescount` | `int` | YES |  |  |
| 1 | `watermask` | `tinyint` | YES |  |  |
| 1 | `babelversion` | `varchar(16382)` | YES |  |  |
| 1 | `lastupdatedtime` | `varchar(16382)` | YES |  |  |
| 1 | `taskqueuename` | `varchar(16382)` | YES |  |  |
| 1 | `timeconsume` | `double` | YES |  |  |
| 1 | `message` | `varchar(16382)` | YES |  |  |
| 1 | `messageforuser` | `varchar(16382)` | YES |  |  |
| 1 | `currentstagename` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_babel_doc_usertasks LIMIT 20;
```
