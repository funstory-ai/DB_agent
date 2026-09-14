# `immdata.imm_user_target_lan_stats`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_user_target_lan_stats` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | ~3.9e7（同步时以 INDEX 为准） |
| 表注释 | 设备 × 翻译目标语累计次数（母语推断上游） |

## 来源与用途（手工维护）

- **数据来源**：Task `update_imm_user_target_lan_stats`（CRON `0 0 21 * * *` UTC）
- **上游**：`user_behaviour`，仅 `event_name = 'translate_page'` 且 `target_language IS NOT NULL`
- **同步方式**：
  - 历史：曾全量 `REPLACE` 按 `(device_id, target_language)` 聚合
  - 现行：按**北京时间昨日**增量 `COUNT`，与旧 `cnt` 相加后 `REPLACE INTO ... ON (device_id, target_language)`
- **更新频率**：日更；应先于 `update_imm_device_native_language`（22:00 UTC）跑完
- **业务含义**：每个设备在各 `target_language` 上的累计网页翻译次数（`translate_page`）
- **建议粒度**：`device_id` × `target_language`
- **主键 / 唯一键**：`(device_id, target_language)`
- **常用过滤**：`target_language IS NOT NULL AND target_language <> ''`
- **关联建议**：主要被 `imm_device_native_language` 取「该设备 cnt Top1 的 target_language」；也可直接做目标语分布（设备级）
- **勿想当然**：
  - 表名含 `user`，实际键是 **`device_id`**，不是注册 userid
  - 只含 `translate_page`，不含 video/image/manga 等
  - 增量窗按北京自然日 → UTC，与裸 `DATE(created_ts)` 不同（P017）
  - 一般分析母语用下游 `imm_device_native_language`，不必每次从本表重算 Top1
  - **按天累计中间表样板（P022）**：新建同类日更汇总可参照本表 TASK + `REPLACE INTO ... ON`；Workspace 看板同类见 `imm_workspace_daily_*`

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `cnt` | `int` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_user_target_lan_stats
ORDER BY update_time DESC
LIMIT 20;
```
