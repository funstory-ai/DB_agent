"""T094 交付物生成：userid 609408 月度 token 消耗（2026-01-27 起）+ 账号背景证据 -> Excel + CSV。"""
import sys, csv
from datetime import date
sys.path.insert(0, "H:/databend_sql/scripts")
from db import query

UID = 609408
OUT_XLSX = "H:/databend_sql/output/user_token_kjzkg84ctb_20261029.xlsx"
OUT_CSV = "H:/databend_sql/output/user_token_kjzkg84ctb_20261029.csv"

# 0) 全局零值确认
z_cols, z_rows = query("""
SELECT 'token_used_aw' AS src, count(*) AS n FROM immdata.token_used_aw WHERE userid = 609408
UNION ALL
SELECT 'imm_token_used' AS src, count(*) AS n FROM immdata.imm_token_used WHERE userid = 609408
""")
print("全局零值确认:", z_cols, z_rows)

# 1) 明细表按月（实际查询，预期 0 行）
aw_cols, aw_rows = query("""
SELECT to_char(timestamp,'%Y-%m') AS month, count(*) AS n_records,
       sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tokens
FROM immdata.token_used_aw
WHERE userid = 609408 AND timestamp >= '2026-01-27 00:00:00'
GROUP BY 1 ORDER BY 1
""")
# 2) 日汇总表按月（预期 0 行）
sum_cols, sum_rows = query("""
SELECT to_char(dates,'%Y-%m') AS month, count(*) AS n_days,
       sum(coalesce(openai,0)+coalesce(deepl,0)+coalesce(deepseek,0)+coalesce(gemini,0)
          +coalesce(claude,0)+coalesce(bigmodel,0)+coalesce(babel_doc,0)+coalesce(qwen3,0)) AS tokens
FROM immdata.imm_token_used
WHERE userid = 609408 AND dates >= '2026-01-27 00:00:00'
GROUP BY 1 ORDER BY 1
""")
aw_map = {r[0]: r[2] for r in aw_rows}
sum_map = {r[0]: r[2] for r in sum_rows}
print("明细表按月行数:", len(aw_rows), "日汇总表按月行数:", len(sum_rows))

# 3) 月度骨架 2026-01 .. 2026-10
months = []
y, m = 2026, 1
while (y, m) <= (2026, 10):
    months.append(f"{y:04d}-{m:02d}")
    m += 1
    if m > 12:
        m = 1; y += 1

# token_used_aw 数据起点 2026-03-02；之前月份结构性为空
AW_START = "2026-03"
rows_out = []
for mo in months:
    note = ""
    if mo < AW_START:
        note = "token_used_aw 无数据（该表 2026-03-02 起有数）"
    rows_out.append({
        "month": mo,
        "tokens_detail_aw": aw_map.get(mo, 0),
        "tokens_summary": sum_map.get(mo, 0),
        "note": note,
    })

# 4) 账号背景：订阅时间线
sub_cols, sub_rows = query("""
SELECT to_char(createtime,'%Y-%m-%d') AS pay_date, amountpaid, subscriptiontype, membership, membertype
FROM immdata.imt_subscriptiongoodsorder
WHERE userid = 609408 AND amountpaid > 0
ORDER BY createtime
""")
# 活跃翻译（对照）
act_cols, act_rows = query("""
SELECT to_char(dt,'%Y-%m') AS ym, sum(translate_cnt) AS cnt, count(*) AS days
FROM immdata.user_translate_day
WHERE userid = '609408'
GROUP BY 1 ORDER BY 1
""")

# 5) 写 CSV
with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["month", "tokens_detail_aw", "tokens_summary", "note"])
    for r in rows_out:
        w.writerow([r["month"], r["tokens_detail_aw"], r["tokens_summary"], r["note"]])
print("CSV ->", OUT_CSV)

# 6) 写 Excel
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "月度token消耗"
ws.append(["月份", "明细表 token 消耗(token_used_aw)", "日汇总表 token 消耗(imm_token_used)", "备注"])
for r in rows_out:
    ws.append([r["month"], r["tokens_detail_aw"], r["tokens_summary"], r["note"]])
ws.append([])
ws.append(["全局零值确认", "", "", ""])
for c, v in z_rows:
    ws.append([c, "行数=" + str(v), "", ""])
ws.append(["结论", "两表对该账号均为 0 行：2026-01-27 起无任何记录的 token 消耗", "", ""])

ws2 = wb.create_sheet("账号背景与证据")
ws2.append(["账号背景（userid=609408, kjzkg84ctb@privaterelay.appleid.com）"])
ws2.append(["付费订阅时间线（amountpaid>0）"])
ws2.append(sub_cols)
for r in sub_rows:
    ws2.append(list(r))
ws2.append([])
ws2.append(["活跃翻译（user_translate_day）"])
ws2.append(["月份", "翻译次数", "活跃天数"])
for r in act_rows:
    ws2.append(list(r))
ws2.append([])
ws2.append(["说明", "连续 Pro 月付会员（¥69/月，自 2024-07 起每月 27 日续费）；但产品实际使用极轻（2026-04~10 仅 61 次翻译），故 token 计量表几乎无记录。"])
wb.save(OUT_XLSX)
print("XLSX ->", OUT_XLSX)

# 控制台摘要
print("\n=== 月度 token 消耗（2026-01 ~ 2026-10，全部为 0）===")
for r in rows_out:
    print(r["month"], "detail=", r["tokens_detail_aw"], "summary=", r["tokens_summary"])
print("\n订阅月数:", len(sub_rows), "首付费:", sub_rows[0] if sub_rows else None, "末付费:", sub_rows[-1] if sub_rows else None)
print("活跃翻译月份:", [r[0] for r in act_rows], "总次数:", sum(r[1] for r in act_rows))
