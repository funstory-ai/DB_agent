# `immdata.user_commercial_intent_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_commercial_intent_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 27232272 |
| 创建时间 | 2026-05-28 08:18:00.174579 |
| 表注释 | 用户每日付费意愿指标：定价页访问 / 限额命中后回访 / 支付流程推进深度 |

## 来源与用途（手工维护）

- **数据来源**：商业意愿相关埋点汇总（付费页曝光 / 限额阻断 / 支付入口等，见表注释）
- **同步方式**：ETL
- **业务含义**：用户每日商业意愿指标
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id
- **勿想当然**：意愿 ≠ 转化；需与订单表交叉验证

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | NO |  | 日期（北京时间） |
| 1 | `userid` | `bigint` | NO |  | 注册用户ID |
| 1 | `pricing_page_visit_cnt` | `int` | NO | 0 | 定价页访问次数（go_pricing_page） |
| 1 | `limit_hit_cnt` | `int` | NO | 0 | 限额命中次数（usage_limit_soft_hit + user_need_pro） |
| 1 | `has_translate_after_limit` | `tinyint` | NO | 0 | 当天限额命中后仍有翻译行为（1=是，0=否） |
| 1 | `paid_order_cnt` | `int` | NO | 0 | 当天真实付费订单数（imt_subscriptiongoodsorder） |
| 1 | `commercial_intent_depth` | `tinyint` | NO | 0 | 付费意愿漏斗深度 0-3 |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_commercial_intent_day LIMIT 20;
```
