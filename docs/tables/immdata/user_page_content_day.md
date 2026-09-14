# `immdata.user_page_content_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_page_content_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 30249761 |
| 创建时间 | 2026-05-28 07:09:14.056510 |
| 表注释 | 用户每日页面内容复杂度汇总，来源 translate_page_leave，按 userid+session_id 去重取最后一条 |

## 来源与用途（手工维护）

- **数据来源**：`translate_page_leave`，按 userid+session_id 去重取最后一次（见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日页面内容复杂度汇总
- **建议粒度**：用户 × 日
- **主键 / 唯一键**：见字段；使用前核对
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：去重规则依赖 session；与 translate 次数口径不同

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | NO |  | 日期（北京时间） |
| 1 | `userid` | `bigint` | NO |  | 注册用户ID |
| 1 | `page_cnt` | `int` | NO | 0 | 当日去重后的翻译页面数（session去重） |
| 1 | `total_char_cnt` | `bigint` | NO | 0 | 当日所有页面字符数之和 |
| 1 | `long_page_cnt` | `int` | NO | 0 | 当日字符数>4800的页面数 |
| 1 | `total_para_cnt` | `bigint` | NO | 0 | 当日所有页面段落数之和 |
| 1 | `total_stay_sec` | `bigint` | NO | 0 | 当日所有页面停留秒数之和 |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_page_content_day LIMIT 20;
```
