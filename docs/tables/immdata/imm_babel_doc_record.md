# `immdata.imm_babel_doc_record`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_babel_doc_record` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 647314 |
| 创建时间 | 2025-02-27 11:32:38.508372 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：BabelDoc 文档翻译用量日汇总（业务侧同步；**非**插件 `user_behaviour`）
- **业务含义**：账号 × 日 × 翻译类型用量；T025 周留存上游
- **建议粒度**：`userid` × `useddate`（可有 `usedcount`）
- **常用过滤**：`userid` 非空；当前 `translatetype` 均为 `babel_doc`
- **关联建议**：留存中间表 `imm_babeldoc_firstuse_weekly_retention`；口径见 `docs/norms/translate_biz.md`
- **勿想当然**：日期已是 `date`，周切分直接 `to_start_of_week(useddate, 1)`；主体是 userid 不是 device_id

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `useddate` | `date` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `usedcount` | `int` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_babel_doc_record LIMIT 20;
```
