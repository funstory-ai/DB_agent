# 查询：免费翻译错误 — `track_translate_page_data` 能否代替弹窗埋点

- **需求编号**: T020
- **规范大类**: `query`
- **状态**: ✅ 已完成
- **日期**: 2026-08-27
- **定稿 SQL**: `sql/reports/query_free_translate_error_tracking_20260827.sql`（短窗分布探查）

- **背景**: 陈琦需区分免费翻译错误是**网络**还是**服务**，以决定国内端点兜底 vs 谷歌兜底；沈超计划加错误弹窗埋点；同事问现有 `track_translate_page_data` 是否可代替
- **插件**: `F:\extension`（本次 `git pull` 失败，读本地仓；首屏译文埋点见 `docs/analytics.md`）

