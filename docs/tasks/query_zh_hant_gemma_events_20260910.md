# 查询：近一月繁中地区 gemma 事件数与占比

- **需求编号**: T034
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-09-10
- **定稿 SQL**: `sql/reports/query_zh_hant_gemma_events_20260910.sql`

## 初始需求

近一个月内，繁中地区 gemma 的事件数以及占比。

## 口径（已确认）

| 项 | 取值 |
|----|------|
| 繁中 | 账号母语 P020，`LOWER(native_language)='zh-tw'` |
| 事件 | 仅 `translate_page` |
| 占比分母 | 同窗同人群全部 `translate_page` |
| 时间窗 | 滚动近 30 天：`[2026-08-11, 2026-09-11)` |
| 交付 | 对话汇总数字 |
| 行为归属 | P016 双路径 |

## gemma 识别（探查结论）

- 插件：`TranslateGemma` 为 `free-model` 子服务（`serviceType=translategemma`，`preferredProvider=translategemma`；繁中界面配置见 `F:\extension\default_config.json`）。`git pull` 失败（GitHub 443），用本地仓核对。
- `user_behaviour.translate_page`：**绝大多数只记 `translation_service='free-model'`**，`ex_char_arg*` 为空，**无法拆分子模型**。
- 全站近 30 天仅出现可识别服务 ID：`free-provider-translategemma`（110 次），且 `interface_language` 全为 `zh-CN`，**不在繁中账号母语 cohort 内**。
- `token_used_aw` 近窗未见 gemma / translategemma 资源名。

因此本题「可识别 gemma」= `translation_service` 含 `gemma` 或 `= free-provider-translategemma`。另附 `free-model` 对照（**不是** gemma 专用）。

## 结果（2026-09-10 跑数）

| 指标 | 值 |
|------|-----|
| 繁中 `translate_page` 总数 | 5,469,731 |
| 可识别 gemma 事件数 | **0** |
| gemma 占比 | **0.00%** |
| （对照）`free-model` 事件数 | 2,723,876 |
| （对照）`free-model` 占比 | 49.80% |

## 抽样复核（P019）

- 全站 30d 可识别 gemma：110；其中繁中账号双路径命中：0；界面 zh-TW/HK：0。通过。
- 主指标两次重跑量级一致（直播流微差）。通过。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 繁中 zh-TW（P020） | SQL `zh_tw` CTE | ✅ |
| 近 30 天 translate_page | 时间窗 + event_name | ✅ |
| gemma 事件数与占比 | 可识别服务 ID；结果 0 / 0% | ✅（注明埋点不可拆子模型） |
| 占比分母=繁中全部 TP | `translate_page_total` | ✅ |
| 对话数字 | 本档 + 对话 | ✅ |
| free-model 对照 | 非需求硬项，附带说明 | ✅ 附 |

## 限制 / 后续可选

若业务要「真实 TranslateGemma 调用量」，需后端把 `preferred_provider` / `provider_id` 落到埋点列，或提供可 join 的用量表；当前 behaviour 无法从 `free-model` 拆出 gemma。
