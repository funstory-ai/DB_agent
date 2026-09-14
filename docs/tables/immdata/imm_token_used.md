# `immdata.imm_token_used`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_token_used` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 6513572 |
| 创建时间 | 2025-07-14 07:04:09.793842 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：Token 消耗汇总/明细（相对较小）
- **同步方式**：ETL 或业务同步
- **业务含义**：模型 token 使用
- **建议粒度**：以字段为准
- **关联建议**：与 `token_used_aw` 区分体量与粒度
- **勿想当然**：不要默认与百亿级 `token_used_aw` 等价

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dates` | `timestamp` | YES |  |  |
| 1 | `userid` | `int` | YES |  |  |
| 1 | `openai` | `int` | YES |  |  |
| 1 | `deepl` | `int` | YES |  |  |
| 1 | `math_pix` | `int` | YES |  |  |
| 1 | `comics` | `int` | YES |  |  |
| 1 | `asr_audio` | `int` | YES |  |  |
| 1 | `pics` | `int` | YES |  |  |
| 1 | `deepseek` | `int` | YES |  |  |
| 1 | `babel_doc` | `int` | YES |  |  |
| 1 | `openai_gpt_41` | `int` | YES |  |  |
| 1 | `gemini_25_pro_preview` | `int` | YES |  |  |
| 1 | `claude4` | `int` | YES |  |  |
| 1 | `novice_ai` | `int` | YES |  |  |
| 1 | `novice_pro_pdf` | `int` | YES |  |  |
| 1 | `novice_asr_audio` | `int` | YES |  |  |
| 1 | `doubao` | `int` | YES |  |  |
| 1 | `bigmodel` | `int` | YES |  |  |
| 1 | `claude` | `int` | YES |  |  |
| 1 | `gemini` | `bigint` | YES |  |  |
| 1 | `qwen3` | `int` | YES |  |  |
| 1 | `bigmodel45air` | `int` | YES |  |  |
| 1 | `qwen_plus` | `int` | YES |  |  |
| 1 | `qwen3_max_preview` | `int` | YES |  |  |
| 1 | `kimi_k2_0905` | `int` | YES |  |  |
| 1 | `silicon` | `int` | YES |  |  |
| 1 | `babel_doc_free_token` | `int` | YES |  |  |
| 1 | `claude__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `claude__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `claude__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `gemini__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `gemini__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `gemini__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `deepl__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `deepl__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `deepl__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `comics__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `comics__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `comics__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `asr_audio__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `asr_audio__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `asr_audio__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `pics__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `pics__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `pics__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `deepseek__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `deepseek__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `deepseek__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `doubao__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `doubao__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `doubao__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `openai_gpt_41__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `openai_gpt_41__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `openai_gpt_41__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `gemini_25_pro_preview__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `gemini_25_pro_preview__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `gemini_25_pro_preview__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `claude4__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `claude4__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `claude4__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `novice_ai__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `novice_ai__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `novice_ai__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `novice_pro_pdf__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `novice_pro_pdf__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `novice_pro_pdf__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `novice_asr_audio__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `novice_asr_audio__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `novice_asr_audio__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `qwen3__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `qwen3__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `qwen3__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel45air__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel45air__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `bigmodel45air__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `openai__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `openai__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `openai__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `math_pix__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `math_pix__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `math_pix__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `qwen_plus__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `qwen_plus__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `qwen_plus__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `kimi_k2_0905__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `kimi_k2_0905__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `kimi_k2_0905__useddate` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc_free_token__useremail` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc_free_token__translatetype` | `varchar(16382)` | YES |  |  |
| 1 | `babel_doc_free_token__useddate` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_token_used LIMIT 20;
```
