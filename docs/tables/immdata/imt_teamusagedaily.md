# `immdata.imt_teamusagedaily`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_teamusagedaily` |
| 类型 | BASE TABLE |
| 约行数 | ~14 万 |
| 表注释 | 租户日用量（按模型/品类） |

## 来源与用途（手工维护）

- **数据来源**：业务库团队用量日汇总
- **业务含义**：每个租户、每天、每个 `modelname`/`categoryname` 一行用量
- **建议粒度**：`tenantid` × `tenantdate` × `modelname`（或 category）
- **主键 / 唯一键**：`id`；业务键看 tenant+date+model
- **常用过滤**：`COALESCE(isdeleted,0)=0`；看板按日期范围滤 `tenantdate`
- **关联建议**：`tenantid` → `imt_teamtenant.id`
- **勿想当然**：
  - **不是**租户×日一行；同一天多模型多行，看板「日用量」必须聚合
  - 同一模型常同时有**汇总行**（如 `Gemini`）与 **`GeminiInput`/`GeminiOutput`**；token 口径=输入+输出时只 SUM Input/Output（或只 SUM 汇总行），**禁止两类一起 SUM**（约 ×2）
  - 主要品类：`OpenAIPro` / `OpenAIMax` 占绝对大头；另有 BabelDoc/Comics/AsrAudio/PdfPro
  - 字段名 `usage` 在部分引擎可能需注意保留字（Databend 当前可直接写）

<!-- AUTO:SCHEMA:START -->
## 字段结构（探查补充）

| # | 字段 | 类型 | 可空 | 注释 |
|---|------|------|------|------|
| 1 | `id` | BIGINT | NO | |
| 1 | `tenantid` | BIGINT | YES | → `imt_teamtenant.id` |
| 1 | `tenantdate` | TIMESTAMP | YES | 用量日（通常 00:00:00） |
| 1 | `modelname` | VARCHAR | YES | 模型名 |
| 1 | `usage` | BIGINT | YES | 用量 |
| 1 | `categoryname` | VARCHAR | YES | 品类（OpenAIPro/OpenAIMax/…） |
| 1 | `isdeleted` | TINYINT | YES | 软删 |

<!-- AUTO:SCHEMA:END -->
