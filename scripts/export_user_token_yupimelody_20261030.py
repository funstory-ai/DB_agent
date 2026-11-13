"""T096 单用户额度消耗分析：yupimelody24@gmail.com (userid=6515557)
窗口 2026-10-22 ~ 2026-10-30（10-30 当日明细尚未同步入库）。
生成 output/user_token_yupimelody_20261030.xlsx。

口径：
- 主体：email 在 imt_subscriptiongoodsorder / imt_deviceinfo 命中，唯一账号 userid=6515557。
  （imt_userinfo 无该邮箱，但订单/设备表一致指向 6515557，按 P018-D 账号级主体。）
- 额度消耗 = token_used_aw 明细表 inputusage+outputusage，成功扣费行 recordtype='capture'。
- 日序列以 imm_token_used（日汇总，缺失 10-26 已回补、较完整）为准；token_used_aw 作交叉校验。
- 时间过滤：token_used_aw 对 timestamp 做范围过滤（P026/P043，禁对时间列套函数）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

UID = 6515557
EMAIL = "yupimelody24@gmail.com"
W0 = "2026-10-22 00:00:00"
W1 = "2026-10-31 00:00:00"  # 含 10-30 当日（若已同步）

OUT = Path(__file__).resolve().parents[1] / "output" / "user_token_yupimelody_20261030.xlsx"


def q(sql):
    cols, rows = query(sql)
    return cols, rows


# ---------- 1. 账号画像 ----------
cols, rows = q(
    f"""SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') AS createtime, isdeleted
        FROM immdata.imt_userinfo WHERE id={UID}"""
)
userinfo = rows[0] if rows else (UID, "n/a", "n/a", None)

# ---------- 2. 订阅/套餐时间线 ----------
cols, rows = q(
    f"""SELECT to_char(createtime,'%Y-%m-%d') AS pay_date, amountpaid, subscriptiontype, membership
        FROM immdata.imt_subscriptiongoodsorder
        WHERE userid={UID} ORDER BY createtime"""
)
sub_rows = rows

# ---------- 3. 日消耗（imm_token_used 日汇总，较完整） ----------
cols, rows = q(
    f"""SELECT to_char(dates,'%Y-%m-%d') AS day,
        coalesce(openai,0)+coalesce(deepl,0)+coalesce(deepseek,0)+coalesce(gemini,0)
        +coalesce(claude,0)+coalesce(bigmodel,0)+coalesce(babel_doc,0)+coalesce(qwen3,0)
        +coalesce(doubao,0)+coalesce(pics,0)+coalesce(asr_audio,0)+coalesce(comics,0)
        +coalesce(math_pix,0)+coalesce(openai_gpt_41,0)+coalesce(gemini_25_pro_preview,0)
        +coalesce(claude4,0)+coalesce(novice_ai,0)+coalesce(qwen_plus,0)+coalesce(kimi_k2_0905,0)
        +coalesce(bigmodel45air,0)+coalesce(novice_pro_pdf,0)+coalesce(novice_asr_audio,0) AS tok
        FROM immdata.imm_token_used
        WHERE userid={UID} AND dates>='2026-10-22' AND dates<'2026-10-31'
        ORDER BY 1"""
)
daily_summary = rows  # (day, tok)

# ---------- 4. 日消耗交叉校验（token_used_aw 明细） ----------
cols, rows = q(
    f"""SELECT to_char(timestamp,'%Y-%m-%d') AS day, count(*) AS n,
        sum(coalesce(inputusage,0)) AS inp, sum(coalesce(outputusage,0)) AS outp,
        sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
        GROUP BY 1 ORDER BY 1"""
)
daily_detail = {r[0]: r for r in rows}

# ---------- 5. 按模型 Provider ----------
cols, rows = q(
    f"""SELECT providername, count(*) AS n,
        sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
        GROUP BY 1 ORDER BY tok DESC"""
)
by_provider = rows

# ---------- 6. 按产品线/类别 ----------
cols, rows = q(
    f"""SELECT productline, categoryname, count(*) AS n,
        sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
        GROUP BY 1,2 ORDER BY tok DESC"""
)
by_pl = rows

# ---------- 7. 时段分布 ----------
cols, rows = q(
    f"""SELECT to_char(timestamp,'%H') AS hr, count(*) AS n,
        sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
        GROUP BY 1 ORDER BY 1"""
)
by_hour = rows

# ---------- 8. 请求体量 ----------
cols, rows = q(
    f"""SELECT count(*) AS n, round(avg(coalesce(inputusage,0)+coalesce(outputusage,0)),0) AS avg_tok,
        max(coalesce(inputusage,0)+coalesce(outputusage,0)) AS max_tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'"""
)
req_stats = rows[0]

# ---------- 9. 对比基准 ----------
cols, rows = q(
    f"""SELECT count(DISTINCT userid) AS active_users,
        sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS total_tok
        FROM immdata.token_used_aw
        WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'"""
)
win_tot = rows[0]
cols, rows = q(
    f"""WITH u AS (
        SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
        GROUP BY 1)
        SELECT count(*) AS users_ge
        FROM u WHERE tok >= (SELECT tok FROM u WHERE userid={UID})"""
)
users_ge = rows[0][0]

this_total = sum(r[1] for r in daily_summary)  # 用日汇总口径
active_users = win_tot[0]
window_total = win_tot[1]

# ================= 写 Excel =================
wb = openpyxl.Workbook()
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=13, color="1F4E78")
BOLD = Font(bold=True)
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER


def setw(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def pct(part, whole):
    return (part / whole * 100) if whole else 0.0


# ---- Sheet 1: 结论与口径 ----
ws = wb.active
ws.title = "结论与口径"
setw(ws, [26, 96])
ws["A1"] = "单用户额度消耗分析 · yupimelody24@gmail.com"
ws["A1"].font = TITLE_FONT
ws.merge_cells("A1:B1")
lines = [
    ("需求编号", "T096 · 规范大类 query · 窗口 2026-10-22 ~ 2026-10-30"),
    ("账号主体", f"userid={UID}（email 在 imt_subscriptiongoodsorder / imt_deviceinfo 命中；imt_userinfo 无该邮箱但两表一致指向 {UID}，账号级主体 P018-D）"),
    ("账号类型", f"accounttype={userinfo[1]}，注册={userinfo[2]}，是否软删={userinfo[3]}"),
    ("会员/套餐", "Pro 月付会员（2026-06 起，约每月 ¥15）；另购两次「package_open_ai_500w」5M-token 套餐：2026-08-19 与 2026-10-22（¥14.99/次）"),
    ("窗口总消耗", f"~{this_total/1e6:.2f}M token（10/22-10/29 连续 8 天，日汇总 imm_token_used 口径）"),
    ("日消耗区间", "约 0.74M（10/22，购套餐当日）~ 1.53M token/日，均值约 1.24M；无突发尖峰"),
    ("按模型", "Google 62.0% / OneRouter 28.9% / OpenAI 7.3% / 其余(BabelFast/Sophnet/DeepL-Pro/DeepSeek 等) <2%"),
    ("按产品线", "全部 web_page · pro-token（网页翻译）；无文档/PDF 等其他线"),
    ("请求形态", f"共 {req_stats[0]:,} 次 capture；单次均值 {req_stats[1]:,.0f} token、最大 {req_stats[2]:,} token —— 小体量、交互式翻译，无批量巨单"),
    ("时段分布", "近 24 小时连续（192 个可能小时中 128 个有量），白天 09-16 点峰值；夜间 00-08 点仍有稳定用量"),
    ("对比基准", f"窗口内 25.1 万活跃用户、合计 24.6B token；本用户 {this_total/1e6:.2f}M 排名约 #{users_ge}（前 {users_ge/active_users*100:.3f}%）——重但属头部，非机器人极端（#1 用户 3.9B，约 400 倍）"),
    ("", ""),
    ("是否正常 · 结论", "属于「重度但正常的头部用户」，未见异常消耗信号。依据：①消耗连续稳定、无尖峰；②单次请求小、呈真实翻译形态；③模型/产品线均为正常网页翻译路由；④相对全量属头部但量级远低于机器人极端值。"),
    ("需注意", "①10/26 在明细表 token_used_aw 一度缺失（ETL 滞后），日汇总 imm_token_used 已回补 0.93M，故无真实断更；②10/30 当日明细尚未同步入库（截至 10-30 16:09），未计入；③5M 套餐按此速率约 4 天耗尽，但用户另有 Pro 月额度+8/19 旧套餐，非硬上限，与「主动复购套餐」自洽。"),
    ("局限（P043）", "token 表只能证明消耗形态，无法判定「人 vs 自动化」——近 24h 连续可能是美区时差重度用户，也可能是翻译工作流/轻量自动化。确证需 user_behaviour 的 UA/请求间隔（本仓仅只读，未拉行为表）。"),
]
r = 3
for k, v in lines:
    ws.cell(row=r, column=1, value=k).font = BOLD
    ws.cell(row=r, column=1).alignment = WRAP
    ws.cell(row=r, column=2, value=v).alignment = WRAP
    r += 1

# ---- Sheet 2: 每日消耗 ----
ws = wb.create_sheet("每日消耗")
setw(ws, [14, 22, 16, 16, 16, 22, 30])
ws.append(["日期", "日汇总 token\n(imm_token_used)", "明细请求数\n(token_used_aw)",
           "明细 input", "明细 output", "明细 token\n(token_used_aw)", "说明"])
style_header(ws, 1, 7)
for day, tok in daily_summary:
    d = daily_detail.get(day)
    if d:
        ws.append([day, tok, d[1], d[2], d[3], d[4], ""])
    else:
        ws.append([day, tok, "—", "—", "—", "—", "明细表该日尚未同步(ETL滞后)；以日汇总为准"])
ws.append(["合计(10/22-10/29)", this_total, "", "", "", "", ""])
ws.cell(row=ws.max_row, column=1).font = BOLD
ws.cell(row=ws.max_row, column=2).font = BOLD
ws.append(["10/30", "（未同步）", "", "", "", "", "截至 10-30 16:09 明细/日汇总均无 10-30 数据"])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 8):
        ws.cell(row=rr, column=cc).border = BORDER

# ---- Sheet 3: 按模型 Provider ----
ws = wb.create_sheet("按模型Provider")
setw(ws, [20, 16, 20, 12])
ws.append(["providername", "请求数", "token", "占比%"])
style_header(ws, 1, 4)
tot = sum(r[2] for r in by_provider)
for p, n, t in by_provider:
    ws.append([p, n, t, round(pct(t, tot), 1)])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 5):
        ws.cell(row=rr, column=cc).border = BORDER

# ---- Sheet 4: 按产品线 ----
ws = wb.create_sheet("按产品线")
setw(ws, [16, 16, 16, 20, 12])
ws.append(["productline", "categoryname", "请求数", "token", "占比%"])
style_header(ws, 1, 5)
tot = sum(r[3] for r in by_pl)
for pl, cat, n, t in by_pl:
    ws.append([pl, cat, n, t, round(pct(t, tot), 1)])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 6):
        ws.cell(row=rr, column=cc).border = BORDER

# ---- Sheet 5: 时段分布 ----
ws = wb.create_sheet("时段分布")
setw(ws, [10, 16, 20, 12])
ws.append(["小时", "请求数", "token", "占比%"])
style_header(ws, 1, 4)
tot = sum(r[2] for r in by_hour)
for hr, n, t in by_hour:
    ws.append([int(hr), n, t, round(pct(t, tot), 1)])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 5):
        ws.cell(row=rr, column=cc).border = BORDER

# ---- Sheet 6: 订阅与套餐 ----
ws = wb.create_sheet("订阅与套餐")
setw(ws, [14, 14, 22, 12])
ws.append(["日期", "实付(分)", "类型", "会员档"])
style_header(ws, 1, 4)
for d, amt, typ, mem in sub_rows:
    ws.append([d, amt, typ, mem])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 5):
        ws.cell(row=rr, column=cc).border = BORDER

# ---- Sheet 7: 对比基准 ----
ws = wb.create_sheet("对比基准")
setw(ws, [30, 26])
ws.append(["指标", "值"])
style_header(ws, 1, 2)
ws.append(["窗口活跃用户数", f"{active_users:,}"])
ws.append(["窗口总 token", f"{window_total:,}"])
ws.append(["本用户窗口 token", f"{this_total:,}"])
ws.append(["本用户排名(>=其用量的人数,含自己)", f"#{users_ge}"])
ws.append(["头部占比", f"前 {users_ge/active_users*100:.3f}%"])
ws.append(["#1 用户窗口 token(对照)", "3,929,147,462"])
for rr in range(2, ws.max_row + 1):
    for cc in range(1, 3):
        ws.cell(row=rr, column=cc).border = BORDER

OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print("SAVED", OUT)
print(f"this_total={this_total:,} active_users={active_users:,} users_ge={users_ge} window_total={window_total:,}")
print(f"req n={req_stats[0]:,} avg={req_stats[1]:,.0f} max={req_stats[2]:,}")
