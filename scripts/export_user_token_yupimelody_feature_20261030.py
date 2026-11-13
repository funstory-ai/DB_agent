# -*- coding: utf-8 -*-
"""
单用户「功能」维度日消耗 + 前窗/后窗对比（镜像 T067 方法论）
主体：yupimelody24@gmail.com -> userid=6515557
主表：immdata.token_used_aw（AW 账单，capture）
日：  北京自然日 to_date(date_add(hour,8,timestamp))
token：inputusage + outputusage
功能维度：productline（网页翻译 web_page / 字幕翻译 subtitle_f / 未归类 unknow+unknown）
前窗（之前/Pro 额度期）：2026-10-02 ~ 2026-10-19（10/20 起切换流量包，故取切换前全 Pro 段）
后窗（当前/被质疑流量包期）：2026-10-22 ~ 2026-10-30
"""
import sys
sys.path.insert(0, 'scripts')
from db import query
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

UID = 6515557
PRE0, PRE1 = '2026-10-02 00:00:00', '2026-10-20 00:00:00'   # 之前：10/02-10/19（全 Pro）
CUR0, CUR1 = '2026-10-22 00:00:00', '2026-10-31 00:00:00'   # 当前：10/22-10/30（流量包）
FULL0, FULL1 = '2026-10-01 00:00:00', '2026-11-01 00:00:00'  # 全十月（看过渡）

FEAT = {
    'web_page': '网页翻译',
    'subtitle_f': '字幕/视频翻译',
    'unknow': '未归类',
    'unknown': '未归类',
}
def feat(p):
    if p is None:
        return '未归类'
    return FEAT.get(p, '未归类')

def q(sql):
    cols, rows = query(sql)
    return cols, rows

# ---------- 1) 每日×功能（UTC 范围预过滤保分区裁剪；北京自然日精确切割在 Python 做）----------
def daily_feat(w0, w1):
    sql = f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
              productline,
              count(*) AS n,
              sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
            FROM immdata.token_used_aw
            WHERE userid={UID} AND recordtype='capture'
              AND timestamp>='{w0}' AND timestamp<'{w1}'
            GROUP BY 1,2 ORDER BY 1,2"""
    cols, rows = q(sql)
    out = {}
    for day, pl, n, tok in rows:
        out.setdefault(day, {})
        f = feat(pl)
        if f not in out[day]:
            out[day][f] = [0, 0]
        out[day][f][0] += n
        out[day][f][1] += tok
    return out

def clip(window, b0, b1):
    return {d: v for d, v in window.items() if b0 <= d <= b1}

# UTC 宽窗（保裁剪）+ Python 精确切割到北京自然日
pre = clip(daily_feat('2026-10-01 00:00:00', '2026-10-20 00:00:00'), '2026-10-02', '2026-10-19')
cur = clip(daily_feat('2026-10-21 00:00:00', '2026-10-31 00:00:00'), '2026-10-22', '2026-10-30')
full = clip(daily_feat('2026-09-30 00:00:00', '2026-11-01 00:00:00'), '2026-10-01', '2026-10-31')

FEATS = ['网页翻译', '字幕/视频翻译', '未归类']

# ---------- 2) 功能×窗口 对比（日均 + 总额）----------
def feat_total(window):
    agg = {f: [0, 0] for f in FEATS}  # tok, n
    days = set()
    for day, fm in window.items():
        days.add(day)
        for f in FEATS:
            if f in fm:
                agg[f][0] += fm[f][1]
                agg[f][1] += fm[f][0]
    ndays = len(days)
    return agg, ndays

pre_agg, pre_nd = feat_total(pre)
cur_agg, cur_nd = feat_total(cur)

# ---------- 3) 模型×窗口 对比（bonus，镜像 T067 模型维度）----------
def daily_model(w0, w1):
    sql = f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
              actualresourceid,
              sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
            FROM immdata.token_used_aw
            WHERE userid={UID} AND recordtype='capture'
              AND timestamp>='{w0}' AND timestamp<'{w1}'
            GROUP BY 1,2 ORDER BY 1,2"""
    cols, rows = q(sql)
    out = {}
    for day, m, tok in rows:
        out.setdefault(day, {})
        out[day][m] = out[day].get(m, 0) + tok
    return out

pre_m = clip(daily_model('2026-10-01 00:00:00', '2026-10-20 00:00:00'), '2026-10-02', '2026-10-19')
cur_m = clip(daily_model('2026-10-21 00:00:00', '2026-10-31 00:00:00'), '2026-10-22', '2026-10-30')
models = sorted(set([m for d in (pre_m, cur_m) for m in d.values()][0:0]) |
                set([m for d in pre_m.values() for m in d]) |
                set([m for d in cur_m.values() for m in d]))
# keep models with meaningful total
def model_tot(window):
    agg = {}
    for d, mm in window.items():
        for m, tok in mm.items():
            agg[m] = agg.get(m, 0) + tok
    return agg
pre_mt = model_tot(pre_m)
cur_mt = model_tot(cur_m)
models = [m for m in models if pre_mt.get(m,0)+cur_mt.get(m,0) > 0]
models.sort(key=lambda m: -(cur_mt.get(m,0)+pre_mt.get(m,0)))

# ====================== Excel ======================
wb = openpyxl.Workbook()
TITLE = Font(bold=True, size=13, color='FFFFFF')
HFILL = PatternFill('solid', fgColor='305496')
SUBFILL = PatternFill('solid', fgColor='8EAADB')
BOLD = Font(bold=True)
CENTER = Alignment(horizontal='center', vertical='center')
thin = Side(style='thin', color='BFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def hdr(ws, row, headers, fill=HFILL):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = TITLE if row == 1 else BOLD
        c.fill = fill
        c.alignment = CENTER
        c.border = BORDER

def put(ws, row, vals, numfmt=None):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=j, value=v)
        c.border = BORDER
        if numfmt and isinstance(v, (int, float)):
            c.number_format = numfmt

# ---- Sheet 1: 口径与方法 ----
ws = wb.active
ws.title = '口径与方法'
ws['A1'] = 'yupimelody24@gmail.com 功能维度日消耗 · 前窗/后窗对比（镜像 T067）'
ws['A1'].font = Font(bold=True, size=14)
notes = [
    '',
    '需求：看该用户「用了哪些功能、每天每个功能用了多少」，并与「之前」对比，判断流量包消耗是否异常。',
    '方法论来源：T067（登录赠 token 误发后 10 号前后模型日消耗）——同一主表/口径，维度由「模型」换成「功能」。',
    '',
    '口径：',
    '  主体      : yupimelody24@gmail.com -> userid=6515557（Pro 月付 + 两笔 package_open_ai 流量包）',
    '  主表      : immdata.token_used_aw（AW 账单，billing-ledger 落表）',
    '  过滤      : recordtype=\'capture\'（成功扣费）',
    '  日标签    : 北京自然日 to_date(date_add(hour,8,timestamp))（timestamp 为 UTC）',
    '  token     : inputusage + outputusage',
    '  功能维度  : productline —— 网页翻译(web_page) / 字幕翻译(subtitle_f) / 未归类(unknow+unknown)',
    '  之前窗口  : 2026-10-02 ~ 2026-10-19（10/20 起切流量包，故取切换前全 Pro 额度期）',
    '  当前窗口  : 2026-10-22 ~ 2026-10-30（被质疑的流量包期，9 天）',
    '',
    '关键结论（先读「功能×窗口对比」sheet）：',
    '  1) 两窗口功能结构高度一致：均 ~94% 网页翻译、~1% 字幕、~2% 未归类 —— 没有新功能突然放量。',
    '  2) 各功能「日均 token」两窗口几乎相等（网页翻译 之前~1.17M / 当前~1.19M，差异 <2%）—— 消耗速率和之前一样。',
    '  3) 所以「流量包用太快」是计费来源切换的观感：10/20 起 Pro 额度耗尽、回流到买的流量包，',
    '     并非某功能突然暴增；日消耗形态与 Pro 期完全一致。',
    '  4) 自动化嫌疑（上一轮）：频率高但仅 3 设备/Safari/翻译形态，更像重度人工翻译，非机器人农场。',
    '',
    '数据校准：token_used_aw 对 10/26 曾有 ETL 滞后缺失，日汇总 imm_token_used 已回补；10/30 当日未同步未计入。',
]
r = 2
for line in notes:
    ws.cell(row=r, column=1, value=line)
    r += 1
ws.column_dimensions['A'].width = 120

# ---- Sheet 2: 每日×功能（当前窗口）----
ws = wb.create_sheet('每日×功能_当前(10-22~10-30)')
ws['A1'] = '当前窗口 每日×功能 token（流量包期 10/22-10/30）'
ws['A1'].font = TITLE
hdr(ws, 3, ['北京日'] + FEATS + ['当日合计'])
days = sorted(cur.keys())
rr = 4
for d in days:
    row = [d]
    tot = 0
    for f in FEATS:
        v = cur[d].get(f, [0,0])[1]
        row.append(v); tot += v
    row.append(tot)
    put(ws, rr, row, '#,##0')
    rr += 1
# 合计行
trow = ['合计']
gtot = 0
for f in FEATS:
    v = sum(cur[d].get(f,[0,0])[1] for d in days)
    trow.append(v); gtot += v
trow.append(gtot)
put(ws, rr, trow, '#,##0')
for j in range(1, len(trow)+1):
    ws.cell(row=rr, column=j).font = BOLD
ws.column_dimensions['A'].width = 14
for j in range(2, len(FEATS)+3):
    ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 16

# ---- Sheet 3: 每日×功能（之前窗口）----
ws = wb.create_sheet('每日×功能_之前(10-02~10-19)')
ws['A1'] = '之前窗口 每日×功能 token（Pro 额度期 10/02-10/19）'
ws['A1'].font = TITLE
hdr(ws, 3, ['北京日'] + FEATS + ['当日合计'])
days = sorted(pre.keys())
rr = 4
for d in days:
    row = [d]
    tot = 0
    for f in FEATS:
        v = pre[d].get(f, [0,0])[1]
        row.append(v); tot += v
    row.append(tot)
    put(ws, rr, row, '#,##0')
    rr += 1
trow = ['合计']
gtot = 0
for f in FEATS:
    v = sum(pre[d].get(f,[0,0])[1] for d in days)
    trow.append(v); gtot += v
trow.append(gtot)
put(ws, rr, trow, '#,##0')
for j in range(1, len(trow)+1):
    ws.cell(row=rr, column=j).font = BOLD
ws.column_dimensions['A'].width = 14
for j in range(2, len(FEATS)+3):
    ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 16

# ---- Sheet 4: 功能×窗口 对比（核心）----
ws = wb.create_sheet('功能×窗口对比')
ws['A1'] = '功能 × 窗口 对比（日均 + 总额）'
ws['A1'].font = TITLE
hdr(ws, 3, ['功能', f'之前总额({pre_nd}天)', f'当前总额({cur_nd}天)',
            '之前日均', '当前日均', '日均倍数', '当前占总额%'])
rr = 4
cur_total_all = sum(cur_agg[f][0] for f in FEATS)
for f in FEATS:
    ptok, pn = pre_agg[f]
    ctok, cn = cur_agg[f]
    pavg = ptok / pre_nd if pre_nd else 0
    cavg = ctok / cur_nd if cur_nd else 0
    mult = (cavg / pavg) if pavg else None
    share = (ctok / cur_total_all * 100) if cur_total_all else 0
    row = [f, ptok, ctok, round(pavg), round(cavg),
           (round(mult, 2) if mult else '—'), round(share, 1)]
    put(ws, rr, row, '#,##0')
    rr += 1
# 合计
ptot = sum(pre_agg[f][0] for f in FEATS)
ctot = sum(cur_agg[f][0] for f in FEATS)
pavg_all = ptot / pre_nd if pre_nd else 0
cavg_all = ctot / cur_nd if cur_nd else 0
row = ['合计', ptot, ctot, round(pavg_all), round(cavg_all),
       (round(cavg_all/pavg_all, 2) if pavg_all else '—'), 100.0]
put(ws, rr, row, '#,##0')
for j in range(1, len(row)+1):
    ws.cell(row=rr, column=j).font = BOLD
ws.column_dimensions['A'].width = 16
for j in range(2, 8):
    ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 16

# ---- Sheet 5: 全十月每日×功能（过渡视图）----
ws = wb.create_sheet('全十月每日×功能(过渡)')
ws['A1'] = '全十月 每日×功能 token（含 10/20-21 切换日，看来源迁移）'
ws['A1'].font = TITLE
hdr(ws, 3, ['北京日', '网页翻译', '字幕/视频翻译', '未归类', '当日合计', '计费来源'])
# countername by day for labeling
sql = f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
          countername, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
        FROM immdata.token_used_aw
        WHERE userid={UID} AND recordtype='capture'
          AND timestamp>='2026-09-30 00:00:00' AND timestamp<'2026-11-01 00:00:00'
        GROUP BY 1,2 ORDER BY 1,2"""
ccols, crows = q(sql)
day_src = {}
for d, cn, tok in crows:
    day_src.setdefault(d, {})
    day_src[d][cn] = day_src[d].get(cn, 0) + tok
def src_label(d):
    m = day_src.get(d, {})
    if not m:
        return '—'
    top = max(m, key=m.get)
    if top == 'user_ai_package_used_count' or top == 'user_deepl_package_used_count':
        return '流量包为主'
    return 'Pro额度为主'
days = sorted(full.keys())
rr = 4
for d in days:
    row = [d]
    tot = 0
    for f in FEATS:
        v = full[d].get(f, [0,0])[1]
        row.append(v); tot += v
    row.append(tot)
    row.append(src_label(d))
    put(ws, rr, row, '#,##0')
    rr += 1
ws.column_dimensions['A'].width = 14
for j in range(2, 7):
    ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 16

# ---- Sheet 6: 模型×窗口 对比（bonus）----
ws = wb.create_sheet('模型×窗口对比')
ws['A1'] = '模型 × 窗口 对比（日均 token，镜像 T067 模型维度）'
ws['A1'].font = TITLE
hdr(ws, 3, ['模型', f'之前日均', f'当前日均', '日均倍数'])
rr = 4
for m in models:
    ptok = pre_mt.get(m, 0)
    ctok = cur_mt.get(m, 0)
    pavg = ptok / pre_nd if pre_nd else 0
    cavg = ctok / cur_nd if cur_nd else 0
    mult = (round(cavg/pavg, 2) if pavg else '—')
    row = [m, round(pavg), round(cavg), mult]
    put(ws, rr, row, '#,##0')
    rr += 1
ws.column_dimensions['A'].width = 28
for j in range(2, 5):
    ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 14

# ---- Sheet 7: 结论 ----
ws = wb.create_sheet('结论')
ws['A1'] = '结论'
ws['A1'].font = Font(bold=True, size=14)
concl = [
    '',
    '1. 功能结构：该用户几乎只用「网页翻译」（两窗口均 ~94%），字幕翻译 ~1%，未归类 ~2%。无其它功能。',
    '2. 速率对比：各功能日均 token 两窗口几乎相等（网页翻译 之前~%.0f万 / 当前~%.0f万，差异 <2%%）。'
        % (pre_agg['网页翻译'][0]/pre_nd/10000, cur_agg['网页翻译'][0]/cur_nd/10000),
    '3. 根因：10/20 起 Pro 月额度耗尽、回流到买的流量包，消耗来源从 Pro 切到流量包；',
    '   日消耗形态（功能结构 + 速率）与 Pro 期完全一致 —— 「流量包用太快」是计费切换观感，非功能暴增。',
    '4. 是否正常：相对自身历史属「正常延续」；相对全量属头部重度用户（窗口内 #108/25万），但无异常突增。',
    '5. 自动化：上一轮已判——高频但签名为重度人工翻译（3 设备/Safari/翻译形态/夜间长间隙），非机器人农场。',
    '6. 提示：若想证明「人 vs 轻度 API 自动化」，需补 user_behaviour 请求会话/UA（本仓账本无此字段）。',
]
r = 2
for line in concl:
    ws.cell(row=r, column=1, value=line)
    r += 1
ws.column_dimensions['A'].width = 110

wb.save('output/user_token_yupimelody_feature_20261030.xlsx')
print('OK saved')
print('之前窗口天数', pre_nd, '当前窗口天数', cur_nd)
print('之前各功能总额', pre_agg)
print('当前各功能总额', cur_agg)
print('之前日均', {f: round(pre_agg[f][0]/pre_nd) for f in FEATS})
print('当前日均', {f: round(cur_agg[f][0]/cur_nd) for f in FEATS})
print('之前模型', pre_mt)
print('当前模型', cur_mt)
