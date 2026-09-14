# `immdata.imm_daily_mmr_by_language`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_daily_mmr_by_language` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 33716 |
| 创建时间 | 2026-07-02 05:00:36.112180 |
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
| 1 | `stat_dt` | `date` | YES |  | 统计日期 |
| 1 | `native_language` | `varchar(16382)` | YES |  | 账号母语，unknown表示未匹配到母语 |
| 1 | `daily_mmr` | `decimal(18, 6)` | YES |  | 当日MMR，已乘以1.09211系数 |
| 1 | `raw_mmr` | `decimal(18, 6)` | YES |  | 原始MMR，未乘以1.09211 |
| 1 | `order_cnt` | `bigint` | YES |  | 参与MMR计算的有效付费订单数 |
| 1 | `user_cnt` | `bigint` | YES |  | 参与MMR计算的有效付费账号数 |
| 1 | `update_time` | `timestamp` | YES |  | 更新时间 |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_daily_mmr_by_language LIMIT 20;
```
