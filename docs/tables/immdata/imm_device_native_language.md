# `immdata.imm_device_native_language`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_device_native_language` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | ~6.8e7（同步时以 INDEX 为准） |
| 表注释 | 设备级推断母语（区分语言类 SQL 主表） |

## 来源与用途（手工维护）

- **数据来源**：日批 Task `update_imm_device_native_language`（CRON `0 0 22 * * *` UTC，约北京时间次日 06:00）
- **上游依赖**：
  1. `imm_user_target_lan_stats`（优先）：设备历史 `translate_page` 的 `target_language` 累计次数 Top1
  2. 当日 `user_behaviour.interface_language`（fallback）：昨日窗内频次 Top1
  3. `imt_deviceinfo`：补 `userid`（按 device 取最新一条）
  4. 昨日窗 `user_behaviour.install_day`：补/收紧 `install_day`（取更早有效安装日）
- **同步方式**：`REPLACE INTO ... ON (device_id)` 增量更新「昨日有行为」的设备；仅当母语/`cnt`/`userid`/`install_day` 变化（或新设备）时写入
- **更新频率**：日更（依赖前序 `update_imm_user_target_lan_stats`，其 CRON 为 21:00 UTC）
- **业务含义**：按设备推断的「母语」标签，用于**按语言拆分**的分析。推断逻辑是 **target_language 优先，否则 interface_language**，不是用户自填母语档案。
- **建议粒度**：**设备一行**（`device_id`）
- **主键 / 唯一键**：业务上按 `device_id` upsert（`ON (device_id)`）
- **常用过滤**：`native_language IS NOT NULL AND native_language <> ''`；按语言筛选时直接滤 `native_language`
- **关联建议**：
  - 埋点：`device_id` = `user_behaviour.device_id`
  - 业务设备：`device_id` = `imt_deviceinfo.deviceid`
  - 表内已有 `userid`（VARCHAR，可能空）；也可再经 `imt_deviceinfo` 桥接
- **勿想当然**：
  - **设备级表**：账号级用 P020——同一 userid 下按语言 **SUM(cnt)**，取最大者为母语
  - `cnt` 含义随来源变：来自 target 时为累计翻译目标语次数；来自 interface fallback 时为昨日窗内该界面语事件次数——**不宜跨来源横比绝对值**
  - `userid` 可空（样例可见）；未登录/未挂上 deviceinfo 的设备仍可能有母语
  - 与 `imm_device_native_language_without_fb`（无 interface fallback）、`vw_user_native_language` 等可能口径不同，按语言拆分时默认用本表
  - 任务增量窗按**北京时间自然日**换算 UTC（`add_hours(date(add_hours(now(),8)), …)`），与 P017 限时原则一致但写法特殊

### 推断口径（任务逻辑摘要）

对「昨日有行为」的 `device_id`：

1. 从 `imm_user_target_lan_stats` 取该设备 `cnt` 最大的 `target_language`（并列按 `update_time`、语言码）
2. 若无，则取昨日窗 `user_behaviour` 中频次最高的 `interface_language`
3. `COALESCE(target, interface)` 非空才保留
4. `install_day`：新旧取更早；`userid`：优先当日 deviceinfo，否则保留旧值

### 账号级归并（已确认，P020）

本表是设备级。账号级母语：

1. 取该 `userid` 下所有设备行
2. 按 `native_language` 对 `cnt` **求和**
3. **合计数最大**的语言 = 该 userid 的母语（并列时可按语言码次序打破，见 pitfalls 示例 SQL）

注意：表内 `userid` 为 VARCHAR 且可空；也可用 `imt_deviceinfo` 桥接后再按同一规则归并。转化类分析仍遵循 P018。

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `cnt` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_device_native_language
ORDER BY update_time DESC
LIMIT 20;
```
