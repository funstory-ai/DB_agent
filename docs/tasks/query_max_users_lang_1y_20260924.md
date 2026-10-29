# 查询：近一年曾 MAX 用户 × 账号母语 × 仍在籍/退订

- **需求编号**: T043
- **规范大类**: `query`
- **状态**: ✅ 已完成（用户验收通过 2026-09-24）
- **日期**: 2026-09-24
- **定稿 SQL**: `sql/reports/query_max_users_lang_1y_20260924.sql`
- **导出**: `scripts/export_t043_max_users_lang.py` → `output/max_users_lang_1y_20260924.xlsx`

## 初始需求

把一年内所有 MAX 用户捞出，标注语言；看语言分布；区分退订与目前仍在会员中。

## 口径（已确认）

| 项 | 定义 |
|----|------|
| MAX 识别 | **`membership='max'`**（与 `subscriptiontype LIKE '%max%'` **完全等价**，近1年 finished 交叉验证 0 差集；`ordertype` 是渠道不是档位） |
| 一年内 | MAX 覆盖期与近 365 天有交集：`cover_end >= now-365d` 且订单 `createtime < now` |
| 计入订单 | `finished` + `subscriptionday>0`；**现金** `amountpaid>0` **或** `ordertype=code` **或** snap `onetime*`；**排除** `trial` / `iospay_trial` / `googleplay_trial` |
| 仍在 MAX | 上述 MAX 单 `MAX(cover_end) >= NOW()` |
| 已退订 | `MAX(cover_end) < NOW()`（未续费导致覆盖结束） |
| 语言 | 账号母语 P020（`imm_device_native_language`，userid 转 BIGINT 后按语 SUM(cnt) 取最大） |
| 交付 | Excel：汇总 / 语言×状态 / 明细一人一行 |

## 交付结果（2026-09-24）

总人数 **5,261**

| MAX状态 | 人数 |
|---------|------|
| 仍在MAX | 3,510 |
| 已退订 | 1,751 |

### 语言分布（Top，账号母语）

| 语言 | 人数 | 占比 |
|------|------|------|
| zh-CN | 3,055 | 58.1% |
| zh-TW | 697 | 13.2% |
| unknown | 493 | 9.4% |
| ko | 279 | 5.3% |
| en | 266 | 5.1% |
| ja | 79 | 1.5% |
| ar | 62 | 1.2% |
| 其它合计 | 330 | 6.3% |

（完整分布见 Excel「汇总」「语言x状态」sheet。）

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 一年内 MAX 用户名单 | 明细 sheet | ✅ |
| 标注语言 | `native_language` | ✅ |
| 语言分布 | 汇总 + 语言×状态 | ✅ |
| 仍在籍 vs 退订 | `max_status` | ✅ |
| 字段确认 membership vs ordertype | 对话+本文口径 | ✅ |

## 抽样复核（正式交付）

抽 20 人（仍在MAX 10 + 已退订 10）：`max_status` / `max_cover_end` 与库重算一致；母语 P020 一致（注意母语表 `userid` 为 VARCHAR，已 CAST）。**通过。**
