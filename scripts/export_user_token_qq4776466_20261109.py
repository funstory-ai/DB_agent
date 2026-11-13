# -*- coding: utf-8 -*-
"""
T104 · 单用户额度消耗异常核查 (v3，镜像 T102 maxime 结构)
主体：4776466@qq.com -> userid=5993459
窗口：2026-05-01 ~ 2026-11-10
主表：immdata.token_used_aw（AW 账单，按天同步，timestamp 为正常事件时间 → 逐日视图有效）

口径（镜像 T102）：
- token = inputusage + outputusage；recordtype='capture'；北京自然日；时间戳正常（数据 owner 确认按天同步）。
- 【服务维度】= productline，映射为「翻译服务类型」：网页翻译(web_page) / 电子书EPUB翻译(epub) /
  PDF翻译 / 字幕视频翻译(subtitle_f) / 文本翻译(text_page) / 漫画(comics) / 未归类(unknow)。
  —— 区别于【上游通道】providername（DashScope/OpenRouter/Sophnet… 是供应商，不是"服务"）。
- 【用量突变对比】：前期基准(05-08~09-18) vs 突变后(10-23 起)，回答"前期均值X、何时开始、升到多少"。
- 额度归属 countername：Pro(user_subs_ai_token_used_count_v2) vs 流量包(user_ai_package_used_count)。
- 自动化检测：(businessid, actionid) 唯一性。
- 行为对照：user_behaviour（真实事件时间，按 device_id 经 imt_deviceinfo 关联）。
"""
import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from db import query
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

UID = 5993459
EMAIL = '4776466@qq.com'
W0, W1 = '2026-05-01 00:00:00', '2026-11-10 00:00:00'

OUT = Path('output') / 'user_token_qq4776466_20261109_v3.xlsx'

CNTR_CN = {
    'user_subs_ai_token_used_count_v2': 'Pro/订阅 AI 额度(20M/月上限)',
    'user_ai_package_used_count': '购买的 AI 流量包(10M)',
    'user_subs_max_ai_used_count': 'Max 年付 AI 额度',
}
# 翻译服务类型（productline）→ 中文；这是用户说的"服务"，不是供应商
FEAT_CN = {
    'epub': '电子书(EPUB)翻译', 'web_page': '网页翻译', 'subtitle_f': '字幕/视频翻译',
    'text_page': '文本翻译', 'comics': '漫画翻译', 'pdf': 'PDF翻译',
    'unknown': '未归类', 'unknow': '未归类', 'verify': '验证',
}


def q(sql):
    cols, rows = query(sql)
    return cols, rows


def pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


# ---------- 1) 账号画像 ----------
c, r = q(f"SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') ct, isdeleted FROM immdata.imt_userinfo WHERE id={UID}")
ui = r[0] if r else (UID, 'n/a', 'n/a', None)

# ---------- 2) 订阅/套餐 ----------
c, r = q(f"""SELECT to_char(createtime,'%Y-%m-%d %H:%M') d, subscriptiontype, membership,
  orderstatus, ordertype, amountpaid, subscriptionday,
  substring(subscriptiongoodssnap, position('OpenAITokenQuota' in subscriptiongoodssnap), 40) snap_quota
FROM immdata.imt_subscriptiongoodsorder WHERE userid={UID} ORDER BY createtime""")
orders = r

# ---------- 3) 月度 × 额度归属(countername) ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m') m, countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2 ORDER BY 1,3 DESC""")
by_mc = r  # (month, cntr, n, tok)

# ---------- 4) 每日消耗（北京日，有效视图） ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, count(*) n,
  sum(coalesce(inputusage,0)) inp, sum(coalesce(outputusage,0)) outp,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY 1""")
daily = r  # (day, n, inp, outp, tok)

# ---------- 5) 每日 × 服务类型(productline) 矩阵（用户要求的「天×服务汇总」） ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, productline, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2 ORDER BY 1,3 DESC""")
day_pl = r  # (day, pl, n, tok)

# ---------- 6) 按服务类型(productline) 总额 ----------
c, r = q(f"""SELECT productline, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY 3 DESC""")
by_pl = r

# ---------- 7) 按上游通道(providername) 总额（注意：这是供应商，不是"服务"） ----------
c, r = q(f"""SELECT providername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY 3 DESC""")
by_prov = r

# ---------- 8) 时段分布（北京小时，有效视图） ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%H') hr, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY 1""")
by_hour = r

# ---------- 9) 自动化检测 ----------
c, r = q(f"""SELECT count(*) total, count(DISTINCT (businessid||'|'||actionid)) distinct_pairs,
  sum(CASE WHEN cnt>1 THEN 1 ELSE 0 END) pairs_repeated, max(cnt) max_repeat
FROM (SELECT businessid, actionid, count(*) cnt
  FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
    AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2) t""")
dup = r[0]
c, r = q(f"""SELECT count(*) n, round(avg(coalesce(inputusage,0)),1) avg_in,
  round(avg(coalesce(outputusage,0)),1) avg_out, max(coalesce(inputusage,0)) max_in,
  median(coalesce(inputusage,0)) med_in, quantile(0.99)(coalesce(inputusage,0)) p99_in
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}'""")
req_stats = r[0]

# ---------- 10) 排名基准 ----------
c, r = q(f"""WITH u AS (SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
  FROM immdata.token_used_aw WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture' GROUP BY 1)
SELECT (SELECT count(*) FROM u WHERE tok>=(SELECT tok FROM u WHERE userid={UID})) rank_no,
       (SELECT count(*) FROM u) total_users,
       (SELECT tok FROM u WHERE userid={UID}) this_tok""")
bench = r[0]
c, r = q(f"""SELECT count(DISTINCT userid), sum(coalesce(inputusage,0)+coalesce(outputusage,0))
FROM immdata.token_used_aw WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'""")
win_tot = r[0]

# ---------- 11) 行为对照（user_behaviour，真实事件时间，按 device 关联） ----------
c, r = q(f"""SELECT deviceid, browser, platform, installchannel, to_char(installtime,'%Y-%m-%d') ct
FROM immdata.imt_deviceinfo WHERE userid={UID} ORDER BY installtime""")
devs = r
dev_ids = [x[0] for x in devs]
beh_rows = []
if dev_ids:
    in_list = "','".join(dev_ids)
    c, r = q(f"""SELECT device_id, event_name, count(*) n
    FROM immdata.user_behaviour WHERE device_id IN ('{in_list}')
      AND created_ts>='2026-05-01' AND created_ts<'2026-11-10'
    GROUP BY 1,2 ORDER BY 1,3 DESC""")
    beh_rows = r

# ================= 突变分析 =================
# 基准期 = 2026-05-08 ~ 2026-09-18（突变前所有批次日）；突变后 = 2026-10-23 起
SPIKE_START = '2026-10-23'
base = [x for x in daily if x[0] <= '2026-09-18']
spike = [x for x in daily if x[0] >= SPIKE_START]
base_tok = sum(x[4] for x in base); base_n = sum(x[1] for x in base); base_days = len(base)
spike_tok = sum(x[4] for x in spike); spike_n = sum(x[1] for x in spike); spike_days = len(spike)
base_avg_tok = base_tok / base_days if base_days else 0
base_avg_n = base_n / base_days if base_days else 0
spike_avg_tok = spike_tok / spike_days if spike_days else 0
spike_avg_n = spike_n / spike_days if spike_days else 0
highest = max(daily, key=lambda x: x[4])            # 最高单日
pre_peak_n = max(base, key=lambda x: x[1])[1]       # 突变前单日请求峰值
post_peak_n = max(spike, key=lambda x: x[1])[1]      # 突变后单日请求峰值
last_base_day = max(base, key=lambda x: x[0])        # 突变前最后基准日
# 月度 token
monthly = {}
for d, n, inp, outp, tok in daily:
    m = d[:7]; monthly[m] = monthly.get(m, 0) + tok

# ================= Excel =================
wb = openpyxl.Workbook()
HEAD_FILL = PatternFill('solid', fgColor='305496')
HEAD_FONT = Font(bold=True, color='FFFFFF')
TITLE_FONT = Font(bold=True, size=13, color='305496')
BOLD = Font(bold=True)
RED = PatternFill('solid', fgColor='FCE4E4')
GRN = PatternFill('solid', fgColor='E2EFDA')
thin = Side(style='thin', color='BFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)


def hdr(ws, row, headers, fill=HEAD_FILL):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = HEAD_FONT; c.fill = fill; c.alignment = CENTER; c.border = BORDER


def put(ws, row, vals, numfmt=None):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=j, value=v)
        c.border = BORDER
        if numfmt and isinstance(v, (int, float)):
            c.number_format = numfmt


def setw(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


pl_total = sum(x[2] for x in by_pl)
prov_total = sum(x[2] for x in by_prov)
mc_total = sum(x[4] for x in daily)
pkg_used = sum(t[3] for t in by_mc if t[1] == 'user_ai_package_used_count')
pkg_remain = 10_000_000 - pkg_used

# ---- Sheet 1: 结论与口径 ----
ws = wb.active; ws.title = '结论与口径'
setw(ws, [26, 106])
ws['A1'] = f'单用户额度消耗分析 · {EMAIL}（userid={UID}）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:B1')
lines = [
    ('需求编号', 'T104 · 规范大类 query（单账号消费异常核查，镜像 T096/T097/T098 方法论 + T102 maxime 结构）'),
    ('账号主体', f'userid={UID}（email 在 imt_userinfo 命中，账号级主体 P018-D）；注册 {ui[2]}，accounttype={ui[1]}，软删={ui[3]}'),
    ('窗口', '2026-05-01 ~ 2026-11-10'),
    ('主表 / 口径', 'immdata.token_used_aw（AW 账单），recordtype=capture，token=input+output；北京自然日；时间戳为正常事件时间（数据 owner 确认，按天同步）→ 逐日/逐小时视图有效。'),
    ('【服务】维度定义', '「服务」= 翻译服务类型 productline（网页翻译/电子书EPUB/PDF/字幕/文本/漫画/未归类），对应 T102 的「每日×功能矩阵」。已更正 v2 误用 providername(上游供应商) 充当"服务"。'),
    ('总消耗', f'{pl_total/1e6:.1f}M token（{sum(x[1] for x in by_pl):,} 次 capture 扣费）'),
    ('功能/服务结构', f'本账号 productline 仅 {FEAT_CN.get(by_pl[0][0], by_pl[0][0])} {pct(by_pl[0][2], pl_total)}% + {FEAT_CN.get(by_pl[-1][0], by_pl[-1][0])} {pct(by_pl[-1][2], pl_total)}%（电子书翻译在此账号记为 unknow 未归类，未打 epub 标签——与 T102 maxime 账号不同，需产品侧补全标签）。'),
    ('额度归属（核心）', '年付 Pro（2026-06-16 起，至 2027-06-16）AI 额度实测≈20M/月硬上限（7–11 月计数器每月恰 20,000,000）；另 2026-06-16 购 10M 流量包，累计已用 {pkg_used:,}（剩 {pkg_remain:,}，{pct(pkg_used,10_000_000)}% 抽干）。'),
    ('异常点（回应客诉）', '重度电子书翻译放大消耗：5–9 月月均≈20M（贴上限）→ 10 月 26M（Pro 20M+包 6M）→ 11 月前 7 天 22M（又撞上限、又抽 2M 包）。用户"额度异常"实为撞破 Pro 上限并抽干流量包，非盗用/重复计费。'),
    ('用量突变（详见「用量突变对比」）', f'前期基准(05-08~09-18)单批次日均值 {base_avg_n:,.0f} 请求 / {base_avg_tok/1e6:.1f}M token；突变开始 {SPIKE_START}（请求从常态几百骤增至 {post_peak_n:,} 条）；最高单日 {highest[0]} = {highest[4]/1e6:.1f}M（一天撞破整月 20M 上限）。'),
    ('自动化检测', f'全部 {dup[0]:,} 条扣费 (businessid,actionid) 全唯一（重复对={dup[2]}）→ 无同请求重发/重试重复计费；单请求 input 中位 {req_stats[4]:,.0f}、p99 {req_stats[5]:,.0f}。10 月出现海量固定≈5.6K 小请求（电子书分段翻译签名），非脚本狂打。'),
    ('排名基准', f'窗口内该用户 {bench[2]/1e6:.1f}M token 排全量第 {bench[0]} 名 / {bench[1]:,} 活跃用户——极重度头部（前 {bench[0]/bench[1]*100:.4f}%）。'),
    ('行为对照', '关联 3 台设备；活跃设备（FF/Win、QQBr/Win，均 CN）在消耗巨大的 10–11 月以浏览/UI 事件为主、无独立 translate_page 峰值——与电子书阅读器走独立路径一致（用户已确认电子书），非盗用信号。'),
    ('待计费/产品侧核实', '① Pro 是否确为 20M/月硬上限；② 电子书翻译是否该走独立额度——建议额度页明示上限，用户即被"超额回退流量包"吓到；③ 流量包类型名写"500w"但订单快照为 10M 的命名不一致；④ 本账号电子书 productline 记为 unknow，需补全标签。'),
    ('局限（P043）', '只读账本只能证明消耗形态；无法判定"是否被多扣"或"分块是否 bug"——需翻译引擎侧（EPUB 分块）与计费侧（额度上限/超量口径）确认。'),
]
r = 3
for k, v in lines:
    ws.cell(row=r, column=1, value=k).font = BOLD
    ws.cell(row=r, column=1).alignment = WRAP
    ws.cell(row=r, column=2, value=v).alignment = WRAP
    if k in ('【服务】维度定义', '异常点（回应客诉）', '用量突变（详见「用量突变对比」）', '待计费/产品侧核实'):
        ws.cell(row=r, column=1).fill = RED
    r += 1

# ---- Sheet 2: 账号与订阅 ----
ws = wb.create_sheet('账号与订阅')
setw(ws, [16, 14, 12, 12, 14, 12, 8])
ws['A1'] = '账号画像 / 订阅套餐历史'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:G1')
ws.append(['账号', ui[0], '类型', ui[1], '注册', ui[2], '软删', ui[3]])
hdr(ws, 3, ['时间', '类型', '会员', '状态', '下单类型', '金额(分)', '天数'])
rr = 4
for d, st, mem, os_, ot, ap, sd, snap in orders:
    put(ws, rr, [d, st, mem, os_, ot, ap, sd], '#,##0'); rr += 1
rr += 1
ws.cell(row=rr, column=1, value='注：2026-06-16 年付 Pro 起（至 2027-06-16）；同日另购 10M 流量包（类型名"500w"，快照 OpenAITokenQuota=10M）。').alignment = WRAP
ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=7)

# ---- Sheet 3: 月度消耗与额度归属 ----
ws = wb.create_sheet('月度消耗与额度归属')
setw(ws, [10, 34, 14, 20, 12])
ws['A1'] = '月度 × 额度归属（countername）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:E1')
months = sorted(set(x[0] for x in by_mc))
cntrs = sorted(set(x[1] for x in by_mc), key=lambda c: -sum(t[3] for t in by_mc if t[1]==c))
pivot = {(m, c): (n, tok) for m, c, n, tok in by_mc}
hdr(ws, 3, ['月份', '额度(countername)', '请求数', 'token', '当月占比%'])
rr = 4
for m in months:
    mtok = sum(pivot[(m, c)][1] for c in cntrs if (m, c) in pivot)
    for c in cntrs:
        if (m, c) in pivot:
            n, tok = pivot[(m, c)]
            put(ws, rr, [m, f'{c}\n({CNTR_CN.get(c,"")})', n, tok, pct(tok, mtok)], '#,##0')
            if 'package' in c or 'ai_package' in c:
                for j in range(1, 6): ws.cell(row=rr, column=j).fill = RED
            rr += 1
    put(ws, rr, [m, '当月合计', sum(pivot[(m,c)][0] for c in cntrs if (m,c) in pivot), mtok, 100.0], '#,##0')
    for j in range(1, 6): ws.cell(row=rr, column=j).font = BOLD
    rr += 1

# ---- Sheet 4: 每日消耗 ----
ws = wb.create_sheet('每日消耗')
setw(ws, [14, 14, 18, 18, 18, 12])
ws['A1'] = '每日消耗（北京自然日，timestamp 有效事件时间）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:F1')
hdr(ws, 3, ['北京日', '请求数', 'input', 'output', 'token', '占比%'])
rr = 4
for d, n, inp, outp, tok in daily:
    fill = RED if d >= SPIKE_START else None
    put(ws, rr, [d, n, inp, outp, tok, pct(tok, mc_total)], '#,##0')
    if fill:
        for j in range(1, 7): ws.cell(row=rr, column=j).fill = fill
    rr += 1
put(ws, rr, ['合计', sum(x[1] for x in daily), sum(x[2] for x in daily), sum(x[3] for x in daily), mc_total, 100.0], '#,##0')
for j in range(1, 7): ws.cell(row=rr, column=j).font = BOLD

# ---- Sheet 5: 每日×服务矩阵（按 productline = 服务类型） ----
ws = wb.create_sheet('每日×服务矩阵')
ws['A1'] = '每日 × 服务类型(productline)：用了几次(count) + 花多少 token'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:H1')
ws['A2'] = '说明：「服务」= 翻译服务类型（网页翻译/电子书/PDF/字幕/文本/漫画/未归类），非上游供应商(providername)。'; ws['A2'].alignment = WRAP; ws.merge_cells('A2:H2')
pls = ['web_page', 'epub', 'pdf', 'subtitle_f', 'text_page', 'comics', 'unknow', 'verify']
days = sorted(set(x[0] for x in day_pl))
# 归一化：unknown 并入 unknow
def norm(p):
    return 'unknow' if p in ('unknow', 'unknown') else p
pivot_pl = {(d, norm(p)): (n, tok) for d, p, n, tok in day_pl}
# 列宽：北京日 + 每服务(次数,token) + 合计(次数,token)
setw(ws, [14] + [12, 14] * len(pls) + [14, 16])
hdr(ws, 4, ['北京日'] + [f'{FEAT_CN.get(p,p)}次数' if i % 2 == 0 else f'{FEAT_CN.get(p,p)}token' for p in pls for i in (0, 1)] + ['当日合计次数', '当日合计token'])
rr = 5
for d in days:
    row = [d]
    dn = dt = 0
    for p in pls:
        n, tok = pivot_pl.get((d, p), (0, 0))
        row += [n, tok]; dn += n; dt += tok
    row += [dn, dt]
    put(ws, rr, row, '#,##0')
    if d >= SPIKE_START:
        for j in range(1, len(row) + 1): ws.cell(row=rr, column=j).fill = RED
    rr += 1
# 服务类型合计行
rr += 1
hdr(ws, rr, ['服务类型合计(全窗)', '', '', '', '', '', '', '', '请求数', 'token']); rr += 1
for p in pls:
    n = sum(v[0] for (dd, pp), v in pivot_pl.items() if pp == p)
    tok = sum(v[1] for (dd, pp), v in pivot_pl.items() if pp == p)
    if n:
        put(ws, rr, [FEAT_CN.get(p, p), '', '', '', '', '', '', '', n, tok], '#,##0'); rr += 1

# ---- Sheet 6: 按服务类型(productline) 总额 ----
ws = wb.create_sheet('按服务类型')
setw(ws, [18, 16, 20, 12])
ws['A1'] = '按翻译服务类型(productline) 总额'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:D1')
hdr(ws, 3, ['服务类型', '请求数', 'token', '占比%'])
rr = 4
for pl, n, tok in by_pl:
    put(ws, rr, [FEAT_CN.get(pl, pl), n, tok, pct(tok, pl_total)], '#,##0'); rr += 1
put(ws, rr, ['合计', sum(x[1] for x in by_pl), pl_total, 100.0], '#,##0')
for j in range(1, 5): ws.cell(row=rr, column=j).font = BOLD

# ---- Sheet 7: 按上游通道 Provider（明确：这是供应商，不是"服务"） ----
ws = wb.create_sheet('按上游通道Provider')
setw(ws, [22, 16, 20, 14])
ws['A1'] = '按上游服务通道(providername) 总额 —— 注意：这是供应商/模型通道，不是「服务类型」'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:D1')
hdr(ws, 3, ['providername', '请求数', 'token', '占比%'])
rr = 4
for svc, n, tok in by_prov:
    put(ws, rr, [svc, n, tok, pct(tok, prov_total)], '#,##0'); rr += 1
put(ws, rr, ['合计', sum(x[1] for x in by_prov), prov_total, 100.0], '#,##0')
for j in range(1, 5): ws.cell(row=rr, column=j).font = BOLD

# ---- Sheet 8: 时段分布 ----
ws = wb.create_sheet('时段分布')
setw(ws, [10, 14, 20, 12])
ws['A1'] = '时段分布（北京小时，timestamp 有效）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:D1')
hdr(ws, 3, ['小时', '请求数', 'token', '占比%'])
rr = 4
for hr, n, tok in by_hour:
    put(ws, rr, [int(hr), n, tok, pct(tok, mc_total)], '#,##0'); rr += 1

# ---- Sheet 9: 自动化检测 ----
ws = wb.create_sheet('自动化检测')
setw(ws, [30, 16, 42])
ws['A1'] = '自动化 / 重复计费检测'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:C1')
hdr(ws, 3, ['检测项', '值', '结论'])
rr = 4
for k, v, note in [('扣费记录总数', dup[0], ''),
                   ('不同 (businessid,actionid) 对数', dup[1], ''),
                   ('重复对(>1次)', dup[2], '=0 → 无同请求重发/重试重复计费'),
                   ('单对最大重复', dup[3], '=1 → 全唯一')]:
    put(ws, rr, [k, v, note]); rr += 1
rr += 1
ws.cell(row=rr, column=1, value='整体单请求统计').font = BOLD; rr += 1
hdr(ws, rr, ['指标', '值', '']); rr += 1
for k, v in [('请求数', req_stats[0]), ('avg input', round(req_stats[1],1)), ('avg output', round(req_stats[2],1)),
             ('max input', req_stats[3]), ('median input', req_stats[4]), ('p99 input', req_stats[5])]:
    put(ws, rr, [k, v, '']); rr += 1

# ---- Sheet 10: 用量突变对比 ----
ws = wb.create_sheet('用量突变对比')
setw(ws, [34, 30, 30, 30])
ws['A1'] = '用量突变对比（前期基准 vs 突变后）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:D1')
ws['A2'] = f'前期基准期 = 2026-05-08 ~ 2026-09-18（突变前所有批次日）；突变开始 = {SPIKE_START}；突变后 = 2026-10-23 ~ 2026-11-07'
ws['A2'].alignment = WRAP; ws.merge_cells('A2:D2')

# 表1 周期级对比
ws.cell(row=4, column=1, value='【表1】周期级对比').font = BOLD
hdr(ws, 5, ['对比维度', '前期基准(05-08~09-18)', '突变后(10-23~11-07)', '变化'])
rr = 6
def addrow(k, a, b, chg, red=False):
    global rr
    put(ws, rr, [k, a, b, chg])
    if red:
        for j in range(1, 5): ws.cell(row=rr, column=j).fill = RED
    rr += 1
addrow('覆盖批次日数', f'{base_days} 天', f'{spike_days} 天', '—')
addrow('累计请求数', f'{base_n:,} 次', f'{spike_n:,} 次', f'3 天≈前期 9 天（{spike_n/base_n*100:.0f}%）')
addrow('累计 token', f'{base_tok/1e6:.1f}M', f'{spike_tok/1e6:.1f}M', '—')
addrow('单批次日平均请求数', f'{base_avg_n:,.0f} 次', f'{spike_avg_n:,.0f} 次', f'×{spike_avg_n/base_avg_n:.1f}', red=True)
addrow('单批次日平均 token', f'{base_avg_tok/1e6:.1f}M', f'{spike_avg_tok/1e6:.1f}M', f'+{(spike_avg_tok/base_avg_tok-1)*100:.0f}%（单请求变小但量更大）')
addrow('月度 token', '约 20M（贴 20M 上限；6 月 41.7M 为早期未限流）', '10 月 26.0M / 11 月前 7 天 22.1M', '突破 20M 上限', red=True)
addrow('是否撞破 Pro 20M/月', '贴着（月均≈20M）', '一天即撞破（11-07 单日 22.05M）', '是', red=True)
addrow('流量包剩余', '10M（未动）', f'剩 {pkg_remain:,} / 10M（抽干 {pct(pkg_used,10_000_000)}%）', '—', red=True)

# 表2 突变节点
rr += 1
ws.cell(row=rr, column=1, value='【表2】突变节点').font = BOLD; rr += 1
hdr(ws, rr, ['项目', '值', '', '']); rr += 1
for k, v in [('突变开始日', f'{SPIKE_START}（请求数从常态几百骤增至 {post_peak_n:,} 条；电子书开始高频分段翻译）'),
             ('突变前最后基准日', f'{last_base_day[0]}（{last_base_day[1]:,} 请求 / {last_base_day[4]/1e6:.1f}M）'),
             ('最高单日 token', f'{highest[0]} = {highest[4]/1e6:.1f}M（史上最高，= 一天耗尽整月 Pro 额度 + 抽 2M 流量包）'),
             ('突变前单日请求峰值', f'{pre_peak_n:,} 条（{max(base,key=lambda x:x[1])[0]}）'),
             ('突变后单日请求峰值', f'{post_peak_n:,} 条（{max(spike,key=lambda x:x[1])[0]}）')]:
    put(ws, rr, [k, v, '', '']); rr += 1

# 表3 月度 token 明细
rr += 1
ws.cell(row=rr, column=1, value='【表3】月度 token 明细（Pro 上限 20M/月）').font = BOLD; rr += 1
hdr(ws, rr, ['月份', 'Pro(20M上限)', '流量包', '合计', '备注']); rr += 1
for m in sorted(monthly.keys()):
    pro = sum(t[3] for t in by_mc if t[0]==m and t[1]=='user_subs_ai_token_used_count_v2')
    pkg = sum(t[3] for t in by_mc if t[0]==m and t[1]=='user_ai_package_used_count')
    note = ''
    if m == '2026-06': note = '早期未限流'
    elif pkg > 0: note = '撞上限+抽包'
    put(ws, rr, [m, pro, pkg, monthly[m], note], '#,##0')
    if pkg > 0:
        for j in range(1, 6): ws.cell(row=rr, column=j).fill = RED
    rr += 1

# ---- Sheet 11: 排名基准 ----
ws = wb.create_sheet('排名基准')
setw(ws, [24, 26])
ws['A1'] = '窗口内消耗量级排名'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:B1')
hdr(ws, 3, ['指标', '值'])
rr = 4
for k, v in [('本用户窗口 token', bench[2]), ('本用户排名', bench[0]), ('活跃用户总数', bench[1]),
             ('头部占比', f'前 {bench[0]/bench[1]*100:.4f}%'), ('窗口总 token', win_tot[1]), ('窗口活跃用户', win_tot[0])]:
    put(ws, rr, [k, v], '#,##0'); rr += 1

# ---- Sheet 12: 行为日志对照 ----
ws = wb.create_sheet('行为日志对照')
setw(ws, [26, 18, 12, 14, 12, 6])
ws['A1'] = '行为日志对照（user_behaviour，真实事件时间，按 device 关联）'; ws['A1'].font = TITLE_FONT; ws.merge_cells('A1:F1')
hdr(ws, 3, ['设备', '浏览器', '平台', 'installchannel', '注册日', ''])
rr = 4
for devid, br, plat, inf, ct in devs:
    put(ws, rr, [devid, br, plat, inf, ct, '']); rr += 1
rr += 1
ws.cell(row=rr, column=1, value='设备 × 事件类型 计数（2026-05-01~11-10）').font = BOLD; rr += 1
hdr(ws, rr, ['设备', '事件类型', '次数', '', '', '']); rr += 1
for devid, ev, n in beh_rows:
    put(ws, rr, [devid, ev, n, '', '', '']); rr += 1
rr += 1
ws.cell(row=rr, column=1, value='注：活跃设备以浏览/UI 事件为主、无独立 translate_page 峰值——与电子书阅读器走独立路径一致（用户已确认电子书），非盗用信号。').alignment = WRAP
ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=6)

OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print('SAVED', OUT)
print('pl_total', f'{pl_total:,}', 'prov_total', f'{prov_total:,}', 'mc_total', f'{mc_total:,}')
print('dup', dup, 'req_stats', req_stats)
print('bench', bench, 'win_tot', win_tot)
print('pkg_used', f'{pkg_used:,}', 'pkg_remain', f'{pkg_remain:,}')
print('base_days', base_days, 'base_n', base_n, 'base_tok', f'{base_tok:,}', 'spike_days', spike_days, 'spike_n', spike_n, 'spike_tok', f'{spike_tok:,}')
print('base_avg_n', round(base_avg_n), 'spike_avg_n', round(spike_avg_n), 'highest', highest[0], highest[4])
print('by_pl', by_pl)
print('devs', [(d[0][:8], d[1], d[2], d[4]) for d in devs])
print('beh_rows count', len(beh_rows))
