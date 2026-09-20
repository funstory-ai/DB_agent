# 查询：日语付费/免费用户翻译引擎排序

- **需求编号**: T040
- **规范大类**: `query`
- **状态**: 进行中（对话结果已出，待验收）
- **日期**: 2026-09-16
- **定稿 SQL**: `sql/reports/query_ja_paid_free_engine_rank_20260916.sql`

## 初始需求

日语用户中，付费与免费用户分别使用最多的引擎；两群组引擎从高到低列几个。

## 口径（已确认）

| 项 | 定义 |
|----|------|
| 时间窗 | 近 30 天 `[2026-08-17, 2026-09-17)` |
| 日语 | 账号母语 P020：`ja` / `ja-%` |
| 付费 | 当前有效会员（同 T008/T036） |
| 免费 | 当前非会员（含过期） |
| 翻译次数 | `user_behaviour`，`event_name='translate_page'` 行数 |
| 引擎 | `translation_service` |
| 归属 | P016 双路径；优先登录 `ex_int_arg1` |
| 交付 | 对话 TopN 汇总 |

人群规模：日语账号 **24,881**（有效会员 **628** / 非会员 **24,253**）。

## 结果（2026-09-16）

### 付费（当前有效会员）— Top10

| 排名 | translation_service | 次数 | 组内占比 |
|------|---------------------|------|----------|
| 1 | **deepl-pro** | 35,713 | 30.9% |
| 2 | openai-pro | 17,603 | 15.2% |
| 3 | gemini-pro | 17,075 | 14.8% |
| 4 | free-model | 9,571 | 8.3% |
| 5 | plamo-pro | 8,789 | 7.6% |
| 6 | google-free | 7,832 | 6.8% |
| 7 | deepseek-pro | 5,360 | 4.6% |
| 8 | babelfast-pro | 5,286 | 4.6% |
| 9 | claude-pro | 3,052 | 2.6% |
| 10 | qwen-pro | 1,753 | 1.5% |

**付费用得最多：deepl-pro。**

### 免费（当前非会员）— Top10

| 排名 | translation_service | 次数 | 组内占比 |
|------|---------------------|------|----------|
| 1 | **free-model** | 301,308 | 60.1% |
| 2 | google-free | 164,847 | 32.9% |
| 3 | bing-free | 7,623 | 1.5% |
| 4 | gemini-custom | 6,500 | 1.3% |
| 5 | openai-custom | 5,651 | 1.1% |
| 6 | openai-pro | 1,907 | 0.4% |
| 7 | plamo-pro | 1,886 | 0.4% |
| 8 | deepl-pro | 1,708 | 0.3% |
| 9 | gemini-pro | 1,576 | 0.3% |
| 10 | deepl-custom | 1,494 | 0.3% |

**免费用得最多：free-model**（其次 google-free，两者合计约 93%）。

## 抽样复核（P019）

付费 Top `deepl-pro` / 免费 Top `free-model` 各抽 10 userid：母语均为 `ja`，会员分组与 `pay_grp` 一致（cover_end 或非会员）。**通过。**

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 付费侧用得最多的引擎 | deepl-pro | ✅ |
| 免费侧用得最多的引擎 | free-model | ✅ |
| 两边从高到低列几个 | Top10 表 | ✅ |
| 对话汇总 | 本档 + 对话 | ✅ |
| 行为表次数非 token | translate_page × translation_service | ✅ |

## 说明

- 仅统计网页主路径 `translate_page`（未含划词/视频等其它 translate_biz 事件）。
- 免费组仍可见少量 `*-pro`：可能为试用、自带 key、或过期前行为落在窗内等，未单独拆解。
