# `immdata.user_translate_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_translate_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 74496131 |
| 创建时间 | 2026-04-08 08:03:24.397054 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：翻译行为按日汇总
- **同步方式**：ETL
- **业务含义**：用户每日翻译次数
- **建议粒度**：`dt` × `userid`
- **主键 / 唯一键**：预期 (`dt`,`userid`)
- **常用过滤**：日期范围
- **关联建议**：注意 **`userid` 类型为 VARCHAR**，与其它表 BIGINT 关联时需显式转换
- **勿想当然**：勿与 `user_translate_attr_day`（多维拆分）直接等价加总而不核对口径

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |
| 1 | `translate_cnt` | `bigint` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_translate_day LIMIT 20;
```
