# `immdata.imm_event_device_count_by_utf8_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_event_device_count_by_utf8_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 15509924 |
| 创建时间 | 2024-10-22 06:54:00.710096 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_event_device_count_by_utf8_day` ← `user_behaviour`（全端，排除 version=1.11.4）
- **同步方式**：日批（北京日前一天，UTC 01:00）
- **更新频率**：每天
- **业务含义**：事件 × 日 × os_name × platform_type × browser_name 的设备数/次数
- **建议粒度**：dates × event_name × os_name × platform_type × browser_name
- **主键 / 唯一键**：TASK `ON (dates, event_name, os_name, platform_type, browser_name)`
- **常用过滤**：必须带 `event_name`；移动端看板先归并 `os_name` 大小写（task8）
- **关联建议**：App 事件近窗安卓是 `android`；插件/浏览器另有 `Android`，设备量更大，不要混当 App
- **勿想当然**：`os_name` 未做大小写归一；`platform_type` 混机型字符串（P009）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dates` | `date` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `device_count` | `bigint unsigned` | NO |  |  |
| 1 | `new_device_count` | `bigint unsigned` | NO |  |  |
| 1 | `event_count` | `bigint unsigned` | NO |  |  |
| 1 | `new_event_count` | `bigint unsigned` | NO |  |  |
| 1 | `update_time` | `timestamp` | NO |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_event_device_count_by_utf8_day LIMIT 20;
```
