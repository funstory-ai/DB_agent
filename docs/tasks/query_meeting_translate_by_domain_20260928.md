# 查询：会议翻译场景分域名

- **需求编号**: T044
- **规范大类**: `query`
- **状态**: ⏸ 搁置（等前端补字段）
- **日期**: 2026-09-28
- **定稿 SQL**: 无（分域名暂不可用）

## 初始需求

看会议翻译场景，分域名看数据；先 pull 插件确认埋点。

## 搁置原因（2026-09-28）

已确认事件 `translate_meeting_video_subtitle` 有数，但 **Zoom / Teams / Google Meet 拆不开**（`video_platform` 未映射、`site_host` 被删、无 meeting performance 旁路）。用户已让前端补传字段；字段落地后再恢复出数。

## 插件查阅

- 路径：`F:\extension`
- **2026-09-28 14:52 已 pull 成功**：`2e1261e7c` → `6c9fd7ff7`（2026-09-28）`add 适配 gem.cbc.ca 字幕`
- 会议/域名相关：**无变化**（`translate_meeting_video_subtitle` 仍不在 `performanceEventNames` / `domainTagGroupEventNames`；`site_host` 仍被主上报 delete）
- 同期 analytics 新内容主要是登录赠额度：`login_ai_quota_gift_*` 字段映射，与会议分域名无关

### 埋点结论

| 项 | 结论 |
|----|------|
| 会议专用事件 | **已有**：`translate_meeting_video_subtitle` |
| 触发条件 | `liveSubtitleRule.isMeeting === true` 时，`reportVideoSubtitle(..., "translate_meeting_video_subtitle")`（`src/video-subtitle/translators/live.ts`） |
| 引入 | commit `b15bca885`（2025-07-17）「会议平台字幕翻译采用单独的上报字段」 |
| 配置站点（`default_config.json` `isMeeting: true`） | **zoom** `*.zoom.us`；**team** `teams.live.com` / `teams.microsoft.com`；**googleMeet** `meet.google.com` |
| 库内是否有数 | 有。短窗 2026-09-21：事件 **2186** 次 / **1344** 设备 |

### 分域名：目前库里对不上

| 候选字段 | 插件侧 | 库内短窗（会议事件） |
|----------|--------|----------------------|
| `domain_tag_group` → `ex_char_arg9` | **仅**挂在 `translate_page` / `translate_video_subtitle`（`report.ts` `domainTagGroupEventNames`），**不含**会议事件 | 全空 |
| `site_host` | `formateSelfReportParams` **主动 delete** | 全空 |
| `video_platform`（规则 id：zoom/team/googleMeet） | `reportVideoSubtitle` 有传，但 **未进** `EXT_MAPPING`，不会落到 `ex_char_arg*` | 行上不可见 |

→ **场景埋点有了，但「分域名/分会议平台」维度当前落不进 `user_behaviour`，正式分域名报表做不了。**

### 网页/视频「带域名」旁路（用户回忆的脱敏通道）

对应的是 `*_performance` 旁路上报（`report.ts` `reportPerformance`），不是主事件上的 `domain_tag_group`：

| 项 | 结论 |
|----|------|
| 白名单事件 | **仅** `translate_page` / `translate_video_subtitle` / `screenshot_area_translate_area_complete` |
| 落库事件名 | `translate_page_performance` / `translate_video_subtitle_performance` / … |
| `site_host` | `formateSelfReportParams` 删完后再 `getDomain(origin)` 写回；库内几乎满填（明文 eTLD+1，如 `youtube.com`） |
| `disableReportHash` | `interface.ts` 有注释「对 site_host 做 hash」，**代码未实现**；当前不是 hash |
| 会议 | **`translate_meeting_video_subtitle` 不在白名单** → **没有** `translate_meeting_video_subtitle_performance`；会议主事件 `site_host` 仍空 |
| 旁证短窗 09-21 | `translate_video_subtitle_performance` 里偶见 `zoom.us`（约 1004 次），不能当会议正式分域名口径（会议走独立事件名） |

## 恢复时口径（待前端字段落地）

| 项 | 候选 |
|----|------|
| 事件 | `translate_meeting_video_subtitle` |
| 分平台 | 优先用前端落到 `ex_char_arg*` 的 `video_platform`（zoom/team/googleMeet）；或 meeting performance + `site_host` |
| 过渡 | 可先出**总分**（不拆平台）UV/次数 |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| pull 插件看埋点 | 本文「插件查阅」 | ✅ |
| 分 Zoom/Teams/Meet 查数 | 等前端补字段 | ⏸ 搁置 |

## 抽样复核

非正式短窗：通过（事件存在；平台/域名字段空）。
