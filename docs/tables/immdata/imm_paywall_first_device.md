# `immdata.imm_paywall_first_device`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_paywall_first_device` |
| 类型 | BASE TABLE（写仓建表） |
| 表注释 | 设备首次付费硬墙（回填窗 2026-05-07 北京起） |

## 来源与用途（手工维护）

- **Task**：`update_imm_paywall_first_device`（近 3 日硬墙事件；**已存在 device 不覆盖**）
- **口径**：`user_need_pro` 且 `trigger='freeUsageLimitModal'`；每 `device_id` 一行，取最早 `created_ts`
- **userid**：`COALESCE(触墙时 ex_int_arg1, imt_deviceinfo.userid)`（P016）
- **lang_bucket**：优先 `imm_device_native_language`，无则回退触墙 `interface_language`（两桶 zh_cn/other）；存量修补见 `task6_paywall_lang_native_patch.sql`
- **DDL**：`sql/reports/task6_paywall_daily_etl.sql`
- **勿想当然**：不是终身全局首次；只从回填下界起算。漏跑某日后靠近 3 日窗补进；更早漏记须重跑回填段
  - `interface_language` 仍保留触墙行原值，**分桶以 `lang_bucket` 为准**
