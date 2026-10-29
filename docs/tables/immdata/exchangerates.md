# `immdata.exchangerates`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.exchangerates` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 45 |
| 创建时间 | 2025-03-07 03:17:28.045594 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：汇率维表（约数十行）
- **同步方式**：维护型小表
- **业务含义**：多币种金额折算
- **建议粒度**：币种
- **关联建议**：订单 `currency` → 本表
- **勿想当然**：确认汇率日期/基准币种后再用于收入汇总
- **规范（P046）**：订单币种匹配不到本表时，收入按「标准人民币价」计，禁止置 `NULL`/`0` 漏算；join 用 `UPPER(currency)` 归一（订单小写、本表大写）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `currency` | `varchar(16382)` | YES |  |  |
| 1 | `exchangerate` | `decimal(10, 5)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.exchangerates LIMIT 20;
```
