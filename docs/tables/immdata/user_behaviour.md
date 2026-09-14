# `immdata.user_behaviour`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_behaviour` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 31875819693 |
| 创建时间 | 2024-09-13 03:12:36.208307 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：沉浸式翻译插件/客户端埋点行为流（最细粒度事件表）
- **同步方式**：持续写入；体量极大（百亿级），查询必须带时间与事件过滤
- **更新频率**：近实时
- **业务含义**：插件侧行为真相源：翻译页、浮球、字幕、弹窗、限额等
- **建议粒度**：`device_id` × `event_name` × `created_ts`（事件行）
- **主键 / 唯一键**：无业务主键；勿对全表 `COUNT(*)` / 无过滤扫描
- **常用过滤**：`created_ts` **必须**用范围比较限时；按需 `event_name` 等
- **性能（硬性）**：
  - 每次查询都要限制时间；并表前先收窄 device / 事件
  - **禁止** `DATE(created_ts)` / 对时间列套函数后再过滤；改用常量上下界：`created_ts >= '...' AND created_ts < '...'`
  - **按天累计看板（P022）**：事件命中少也可能数十秒；须实测。Workspace 看板读 `imm_workspace_daily_*`；付费墙看板读 `imm_paywall_daily_*`（写仓后），勿挂 90d 直查
- **关联建议**：与注册用户/订单关联须 **双路径（P016）**：① `imt_deviceinfo.deviceid` = `device_id`；② `ex_int_arg1` = userid（登录才有，P006）。两路合并，勿只用其一。
- **实体关系**：存在单账户多设备、单设备多账户；转化类指标需先定 user/device 口径与去重
- **Workspace 相关事件（task5）**：前缀 `workspace_*`（如 `workspace_open` / `workspace_translate_click` / `workspace_translate_success` / `workspace_translate_fail` 等）；日更汇总见 `imm_workspace_daily_kpi`、`imm_workspace_daily_dim`
- **付费硬墙（task6）**：日常触墙仅 `user_need_pro` 且 `trigger='freeUsageLimitModal'`。日更见 `imm_paywall_daily_kpi` / `imm_paywall_daily_wide_*`
- **勿想当然**：
  - `install_day` 可能出现 `1970-01-01`（占位），不能当真实安装日
  - `user_type` 含 `anonymous` / `free` / 会员档位等，口径需先对齐业务
  - `platform_type` 除 desktop/mobile/tablet 外，可能混入 iPhone 机型字符串
  - `ex_char_arg*` / `ex_int_arg*` 含义随 `event_name` 变化，必须查表文档或埋点说明
  - 存在拼写异常事件名如 `translage_page_daily`

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `ab_group` | `varchar(16382)` | YES |  |  |
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `real_ip` | `varchar(16382)` | YES |  |  |
| 1 | `real_geo` | `varchar(16382)` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `trigger` | `varchar(16382)` | YES |  |  |
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `always_translate_languages` | `varchar(16382)` | YES |  |  |
| 1 | `beta` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `browser_version` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `enable_default_always_translated_urls` | `varchar(16382)` | YES |  |  |
| 1 | `enable_input_translation` | `varchar(16382)` | YES |  |  |
| 1 | `engine_name` | `varchar(16382)` | YES |  |  |
| 1 | `engine_version` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `varchar(16382)` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `install_week` | `varchar(16382)` | YES |  |  |
| 1 | `interface_language` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_month` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_week` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_year` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_today` | `varchar(16382)` | YES |  |  |
| 1 | `main_frame` | `int` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `os_version` | `varchar(16382)` | YES |  |  |
| 1 | `os_version_name` | `varchar(16382)` | YES |  |  |
| 1 | `page_type` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `site_host` | `varchar(16382)` | YES |  |  |
| 1 | `source_language` | `varchar(16382)` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `temp_translate_domain_minutes` | `bigint` | YES |  |  |
| 1 | `translation_area` | `varchar(16382)` | YES |  |  |
| 1 | `translation_mode` | `varchar(16382)` | YES |  |  |
| 1 | `translation_service` | `varchar(16382)` | YES |  |  |
| 1 | `translation_theme` | `varchar(16382)` | YES |  |  |
| 1 | `user_type` | `varchar(16382)` | YES |  |  |
| 1 | `userscript` | `varchar(16382)` | YES |  |  |
| 1 | `version` | `varchar(16382)` | YES |  |  |
| 1 | `created_ts` | `timestamp` | YES |  |  |
| 1 | `ex_char_arg1` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg2` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg3` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg4` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg5` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg6` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg7` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg8` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg9` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg10` | `varchar(16382)` | YES |  |  |
| 1 | `ex_int_arg1` | `int` | YES |  |  |
| 1 | `ex_int_arg2` | `int` | YES |  |  |
| 1 | `ex_int_arg3` | `int` | YES |  |  |
| 1 | `ex_int_arg4` | `int` | YES |  |  |
| 1 | `ex_int_arg5` | `int` | YES |  |  |
| 1 | `ex_int_arg6` | `int` | YES |  |  |
| 1 | `ex_int_arg7` | `int` | YES |  |  |
| 1 | `ex_int_arg8` | `int` | YES |  |  |
| 1 | `ex_int_arg9` | `int` | YES |  |  |
| 1 | `ex_int_arg10` | `int` | YES |  |  |
| 1 | `real_city` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_behaviour LIMIT 20;
```
