# `immdata.imm_app_active_new_device_by_os_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_app_active_new_device_by_os_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 175 |
| 创建时间 | 2026-07-17 11:19:50.122241 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：TASK `task_daily_app_active_new_device_by_os` ← `user_behaviour`（`event_name='app_active'` 且当日新用户）
- **同步方式**：日批（北京日前一天）
- **更新频率**：每天
- **业务含义**：App `app_active` 新设备数，按日 × 系统
- **建议粒度**：dates × os_name
- **主键 / 唯一键**：dates + os_name（TASK 按日 DELETE 再 INSERT）
- **常用过滤**：看板请先把 `os_name` 归并大小写（见 task8）
- **关联建议**：勿与插件 `Android` 行直接对拍
- **勿想当然**：`os_name` 安卓侧是小写 `android`，iOS/iPadOS 是 Title Case；过滤 `Android` 会空

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dates` | `date` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `device_count` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_app_active_new_device_by_os_day LIMIT 20;
```
