# `immdata.user_translate_attr_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_translate_attr_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 77334668 |
| 创建时间 | 2026-04-08 12:58:36.073167 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：翻译行为按日 + 属性维度汇总
- **同步方式**：ETL
- **业务含义**：平台/浏览器/OS/目标语言等维度下的翻译次数
- **建议粒度**：`dt` × `userid` × 属性维
- **主键 / 唯一键**：多维组合键
- **常用过滤**：`dt`；维度枚举
- **关联建议**：`userid` BIGINT
- **勿想当然**：同一用户一天多行；`SUM(translate_cnt)` 按维展开，不要与日表不加区分直接对比

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `translate_cnt` | `bigint` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_translate_attr_day LIMIT 20;
```
