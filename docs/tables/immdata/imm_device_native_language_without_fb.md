# `immdata.imm_device_native_language_without_fb`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_device_native_language_without_fb` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | ~3.5e7（同步时以 INDEX 为准） |
| 表注释 | 设备母语（无 interface_language fallback） |

## 来源与用途（手工维护）

- **数据来源**：Databend TASK `update_imm_device_native_language_without_fb`（CRON `0 30 22 * * *` UTC，约北京 06:30；2026-10-20 起）。表名 `without_fb` = **without fallback**
- **上游**：只收「北京昨日」有 `translate_page` 且 `target_language` 非空的设备，再取 `imm_user_target_lan_stats` 里 cnt 最大的目标语。`install_day` 取行为里更早的合法安装日
- **业务含义**：只用翻译目标语推断母语，**不用** `interface_language` 兜底。2026-10-20 之前任务在 20:00 UTC，早于目标语累计（21:00 UTC），只译当天的设备进不来（T078）。现已改到 22:30 UTC，并按累计表补过历史缺行。补完后主表仍会比本表大，多出来的是没有目标语累计的设备（2026-09 安装月：简中主表 2,002,195、本表 715,551，多出的 1,285,080 在 `imm_user_target_lan_stats` 无行；英语更夸张，主表 829,237 里 766,937 无目标语）
- **建议粒度**：设备一行（`device_id`）
- **主键 / 唯一键**：`ON (device_id)`
- **关联建议**：同主表；**默认按语言拆分用 `imm_device_native_language`**，本表仅在明确要求「不要 UI 语言兜底」且接受「漏掉只活跃一天的设备」时使用
- **勿想当然**：无 `userid` 列；这不是 P034 激活（`translate_page` + `is_new_user_today`）。按 `install_day` 分月是安装日队列，不是当天激活人数
- **修复**：写仓脚本 `sql/reports/anomaly_t078_without_fb_task_fix.sql`。2026-10-20 补数已进表；任务已改为 `0 30 22 * * *` UTC（北京 06:30），在累计任务 21:00 UTC 之后。`last_committed` 2026-10-20 12:02 UTC

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `cnt` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_device_native_language_without_fb
ORDER BY update_time DESC
LIMIT 20;
```
