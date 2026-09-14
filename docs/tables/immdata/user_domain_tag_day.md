# `immdata.user_domain_tag_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_domain_tag_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 44077557 |
| 创建时间 | 2026-05-28 07:14:41.043528 |
| 表注释 | 用户每日域名标签汇总，来源 translate_page.ex_char_arg9=domain_tag_group，上报率约1.76%，只作正向信号 |

## 来源与用途（手工维护）

- **数据来源**：`translate_page.ex_char_arg9=domain_tag_group` 汇总；表注释称上报率约 1.76%
- **同步方式**：ETL
- **业务含义**：用户每日域名标签翻译次数（research/dev/collab 等）
- **建议粒度**：`dt` × `userid`
- **主键 / 唯一键**：预期 (`dt`,`userid`)
- **常用过滤**：日期；只作正向信号（低上报率）
- **关联建议**：`userid` → 用户
- **勿想当然**：**不能**外推为全体用户域名偏好；未上报用户缺失

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | NO |  | 日期（北京时间） |
| 1 | `userid` | `bigint` | NO |  | 注册用户ID |
| 1 | `research_cnt` | `int` | NO | 0 | 高价值研究域名翻译次数（domain_tag_group=research） |
| 1 | `dev_cnt` | `int` | NO | 0 | 高价值开发域名翻译次数（domain_tag_group=dev） |
| 1 | `collab_cnt` | `int` | NO | 0 | 商务协作域名翻译次数（domain_tag_group=collab） |
| 1 | `commerce_cnt` | `int` | NO | 0 | 跨境商业域名翻译次数（domain_tag_group=commerce） |
| 1 | `finance_cnt` | `int` | NO | 0 | 财经信息域名翻译次数（domain_tag_group=finance） |
| 1 | `high_value_total_cnt` | `int` | NO | 0 | 所有高价值域名翻译次数之和 |
| 1 | `total_translate_page_cnt` | `int` | NO | 0 | 当日总 translate_page 事件数（com口径，非移动端） |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_domain_tag_day LIMIT 20;
```
