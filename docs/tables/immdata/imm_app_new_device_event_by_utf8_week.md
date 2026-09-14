# `immdata.imm_app_new_device_event_by_utf8_week`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_app_new_device_event_by_utf8_week` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 5229675 |
| 创建时间 | 2025-09-22 02:55:07.421624 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_app_new_device_event_by_utf8_week` ← `user_behaviour`（App 周设备事件）
- **同步方式**：周批（周一 UTC）
- **更新频率**：每周
- **业务含义**：设备 × 事件 × 周；`app_active` 的 `browser_version` 被 TASK 写成 `ALL`
- **建议粒度**：week_start_day × event_name × device_id × os_name × browser_version
- **主键 / 唯一键**：TASK `ON (week_start_day, event_name, device_id, os_name, browser_version)`
- **常用过滤**：`event_name`；看板 `os_name` 须大小写归并（task8）
- **关联建议**：留存用 `install_week_start_day` vs `week_start_day`
- **勿想当然**：`app_active` 的 `os_name` 安卓侧是小写 `android`（不是 `Android`）；`browser_version='ALL'`，`>= '2.0.0'` 字符串比较对 ALL 恒真

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `week_start_day` | `date` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `install_week_start_day` | `date` | YES |  |  |
| 1 | `event_count` | `bigint unsigned` | NO |  |  |
| 1 | `update_time` | `timestamp` | NO |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `browser_version` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_app_new_device_event_by_utf8_week LIMIT 20;
```
