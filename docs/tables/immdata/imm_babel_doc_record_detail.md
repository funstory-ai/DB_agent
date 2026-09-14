# `immdata.imm_babel_doc_record_detail`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_babel_doc_record_detail` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 2236586 |
| 创建时间 | 2025-03-25 09:48:48.140716 |
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
| 1 | `pdfhash` | `varchar(16382)` | YES |  |  |
| 1 | `filename` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `int` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `totalpagescount` | `int` | YES |  |  |
| 1 | `totalusedpagescount` | `int` | YES |  |  |
| 1 | `token_count` | `int` | YES |  |  |
| 1 | `recordid` | `varchar(16382)` | YES |  |  |
| 1 | `recordtype` | `varchar(16382)` | YES |  |  |
| 1 | `sourcelanguage` | `varchar(16382)` | YES |  |  |
| 1 | `targetlanguage` | `varchar(16382)` | YES |  |  |
| 1 | `requestmodel` | `varchar(16382)` | YES |  |  |
| 1 | `actualmodel` | `varchar(16382)` | YES |  |  |
| 1 | `task_info` | `varchar(16382)` | YES |  |  |
| 1 | `prostatus` | `varchar(16382)` | YES |  |  |
| 1 | `id` | `varchar(16382)` | YES |  |  |
| 1 | `task_type` | `varchar(16382)` | YES |  |  |
| 1 | `prompt_token` | `bigint` | YES |  |  |
| 1 | `completion_token` | `bigint` | YES |  |  |
| 1 | `total_token_include_cache` | `bigint` | YES |  |  |
| 1 | `prompt_token_include_cache` | `bigint` | YES |  |  |
| 1 | `completion_token_include_cache` | `bigint` | YES |  |  |
| 1 | `withhold_token` | `bigint` | YES |  |  |
| 1 | `peakmemoryusage` | `double` | YES |  |  |
| 1 | `enhance_compatibility` | `tinyint` | YES |  |  |
| 1 | `ocrworkaround` | `tinyint` | YES |  |  |
| 1 | `backendstatus` | `varchar(16382)` | YES |  |  |
| 1 | `primaryfontfamily` | `varchar(16382)` | YES |  |  |
| 1 | `autoenableocrworkaround` | `tinyint` | YES |  |  |
| 1 | `only_include_translated_page` | `tinyint` | YES |  |  |
| 1 | `disable_rich_text_translate` | `tinyint` | YES |  |  |
| 1 | `output_file_prefix` | `varchar(16382)` | YES |  |  |
| 1 | `layout_model_id` | `varchar(16382)` | YES |  |  |
| 1 | `merge_alternating_line_numbers` | `tinyint` | YES |  |  |
| 1 | `remove_non_formula_lines` | `tinyint` | YES |  |  |
| 1 | `dual_mode` | `varchar(16382)` | YES |  |  |
| 1 | `ate_token_total` | `bigint` | YES |  |  |
| 1 | `ate_token_prompt` | `bigint` | YES |  |  |
| 1 | `ate_token_completion` | `bigint` | YES |  |  |
| 1 | `ate_token_total_include_cache` | `bigint` | YES |  |  |
| 1 | `ate_token_prompt_include_cache` | `bigint` | YES |  |  |
| 1 | `ate_token_completion_include_cache` | `bigint` | YES |  |  |
| 1 | `pdf_total_char_count` | `bigint` | YES |  |  |
| 1 | `pdf_total_char_token_count` | `bigint` | YES |  |  |
| 1 | `autoextractglossaryfilekey` | `varchar(16382)` | YES |  |  |
| 1 | `model_usage_info` | `varchar(16382)` | YES |  |  |
| 1 | `tasks` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_babel_doc_record_detail LIMIT 20;
```
