# `immdata.imm_app_new_event_device_count_by_utf8_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_app_new_event_device_count_by_utf8_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 783015 |
| 创建时间 | 2025-09-22 04:02:21.548633 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_app_new_event_device_count_by_utf8_day`（App browser_name 白名单）+ `update_imm_app_new_event_device_count_by_utf8_day_extension`（`app_active`，且 `android→Android`）
- **同步方式**：日批（北京日前一天）
- **更新频率**：每天
- **业务含义**：App 事件按日 × os × 浏览器版本的设备数/次数
- **建议粒度**：dates × event_name × os_name × browser_version × browser_name
- **主键 / 唯一键**：主 TASK `ON (dates, event_name, os_name, browser_version, browser_name)`；extension 仅 `ON (dates, event_name, os_name)`
- **常用过滤**：`os_name` 近窗已是 `Android`/`iOS`/`iPadOS`（看板仍建议套 CASE，见 task8）
- **关联建议**：与 `imm_event_device_count_by_utf8_day` 的小写 `android` 不是同一写法
- **勿想当然**：extension 只归一了 `app_active`；其它事件靠埋点本身的 Title Case

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dates` | `date` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `browser_version` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `device_count` | `bigint unsigned` | NO |  |  |
| 1 | `new_device_count` | `bigint unsigned` | NO |  |  |
| 1 | `event_count` | `bigint unsigned` | NO |  |  |
| 1 | `new_event_count` | `bigint unsigned` | NO |  |  |
| 1 | `update_time` | `timestamp` | NO |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_app_new_event_device_count_by_utf8_day LIMIT 20;
```
