# -*- coding: utf-8 -*-
"""
T102 · 单用户功能使用 / 消费异常核查
主体：maximefouquet33@gmail.com -> userid=7154600
窗口：2026-09-01 ~ 2026-11-04（首次用量 9/26，截至数据 11/02）
主表：immdata.token_used_aw（AW 账单，billing-ledger 落表，capture=成功扣费）
背景：用户提交双语工单，反映 EPUB（电子书）翻译 token 消耗异常、Book B/C 每页消耗≈A 的 2.6 倍，
      并问 5 个问题（token 怎么计 / 有无按书明细 / 重试续翻是否重复计 / 近期计数或分组是否变 / 多扣能否退）。

口径：
- 主体：email 在 imt_userinfo 命中（oauth，2026-09-01 注册），订单/设备表一致指向 userid=7154600（账号级主体 P018-D）。
- token = inputusage + outputusage；过滤 recordtype='capture'。
- 日标签：北京自然日 to_char(date_add(hour,8,timestamp),'%Y-%m-%d')（timestamp 为 UTC）；WHERE 用粗 UTC 范围保分区裁剪。
- 功能维度：productline（epub=电子书翻译，web_page=网页翻译，subtitle_f=字幕，unknown/unknow=未归类）。
- 重复计费检测：(businessid, actionid) 唯一性。
"""
import sys
sys.path.insert(0, 'scripts')
from db import query
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

UID = 7154600
EMAIL = 'maximefouquet33@gmail.com'
W0, W1 = '2026-09-01 00:00:00', '2026-11-04 00:00:00'

FEAT_CN = {
    'epub': '电子书(EPUB)翻译',
    'web_page': '网页翻译',
    'subtitle_f': '字幕/视频翻译',
    'unknown': '未归类',
    'unknow': '未归类',
    'verify': '验证',
    'text_page': '文本翻译',
    'comics': '漫画',
}
CNTR_CN = {
    'user_subs_ai_token_used_count_v2': 'Pro/订阅 AI 额度',
    'user_subs_max_ai_used_count': 'Max 年付 AI 额度',
    'user_subs_deep_l_used_count_v2': '订阅 DeepL 额度',
    'user_subs_math_pixused_count_v2': '订阅 Mathpix',
    'user_subs_comics_page_used_count_v2': '订阅 漫画页',
    'babel_doc_page': '文档页',
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

# ---------- 3) 功能维度（productline）总额 ----------
c, r = q(f"""SELECT productline, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY tok DESC""")
by_pl = r
pl_total = sum(x[2] for x in by_pl)

# ---------- 4) 每日×功能 矩阵 ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, productline,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2 ORDER BY 1,2""")
day_pl = r  # (day, pl, tok)

# ---------- 5) 额度归属 countername ----------
c, r = q(f"""SELECT countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY tok DESC""")
by_cntr = r

# ---------- 6) 按模型 providername ----------
c, r = q(f"""SELECT providername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY tok DESC""")
by_prov = r

# ---------- 7) EPUB 专项：每日 单请求 input/output ----------
c, r = q(f"""SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, count(*) n,
  round(avg(coalesce(inputusage,0)),0) avg_in, round(avg(coalesce(outputusage,0)),0) avg_out,
  round(avg(coalesce(inputusage,0)+coalesce(outputusage,0)),0) avg_tot,
  max(coalesce(inputusage,0)) max_in
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1 ORDER BY 1""")
epub_by_day = r

# ---------- 8) EPUB 模型 actualresourceid ----------
c, r = q(f"""SELECT actualresourceid, providername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2 ORDER BY tok DESC LIMIT 25""")
epub_model = r

# ---------- 9) EPUB 重复计费检测 ----------
c, r = q(f"""SELECT count(*) total, count(DISTINCT (businessid||'|'||actionid)) distinct_pairs,
  sum(CASE WHEN cnt>1 THEN 1 ELSE 0 END) pairs_repeated, max(cnt) max_repeat
FROM (SELECT businessid, actionid, count(*) cnt
  FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
    AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2) t""")
epub_dup = r[0]

# ---------- 10) EPUB input 分桶 ----------
c, r = q(f"""SELECT
  sum(CASE WHEN coalesce(inputusage,0)=0 THEN 1 ELSE 0 END) in_zero,
  sum(CASE WHEN coalesce(inputusage,0) BETWEEN 1 AND 1000 THEN 1 ELSE 0 END) in_1_1k,
  sum(CASE WHEN coalesce(inputusage,0) BETWEEN 1001 AND 5000 THEN 1 ELSE 0 END) in_1k_5k,
  sum(CASE WHEN coalesce(inputusage,0) BETWEEN 5001 AND 20000 THEN 1 ELSE 0 END) in_5k_20k,
  sum(CASE WHEN coalesce(inputusage,0) > 20000 THEN 1 ELSE 0 END) in_gt20k
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
  AND timestamp>='{W0}' AND timestamp<'{W1}'""")
epub_bkt = r[0]

# ---------- 11) EPUB provider/countername ----------
c, r = q(f"""SELECT providername, countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
  AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY 1,2 ORDER BY tok DESC LIMIT 20""")
epub_pc = r

# ---------- 12) EPUB 整体 per-request 分布 ----------
c, r = q(f"""SELECT count(*) n, round(avg(coalesce(inputusage,0)),1) avg_in,
  round(avg(coalesce(outputusage,0)),1) avg_out,
  max(coalesce(inputusage,0)) max_in, median(coalesce(inputusage,0)) med_in,
  quantile(0.99)(coalesce(inputusage,0)) p99_in
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture' AND productline='epub'
  AND timestamp>='{W0}' AND timestamp<'{W1}'""")
epub_stats = r[0]

# ---------- 13) 排名基准 ----------
c, r = q(f"""WITH u AS (SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
  FROM immdata.token_used_aw WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture' GROUP BY 1)
SELECT (SELECT count(*) FROM u WHERE tok>=(SELECT tok FROM u WHERE userid={UID})) rank_no,
       (SELECT count(*) FROM u) total_users,
       (SELECT tok FROM u WHERE userid={UID}) this_tok""")
bench = r[0]
c, r = q(f"""SELECT count(DISTINCT userid), sum(coalesce(inputusage,0)+coalesce(outputusage,0))
FROM immdata.token_used_aw WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'""")
win_tot = r[0]

# 早期 vs 近期 EPUB 单请求 input 均值（异常量化）
early = [x for x in epub_by_day if x[0] <= '2026-10-03']   # Book A 期（早期）
late = [x for x in epub_by_day if x[0] >= '2026-10-31']     # 近期书（10/31-11/02）
early_in = sum(x[2]*x[1] for x in early)/sum(x[1] for x in early) if early else 0
late_in = sum(x[2]*x[1] for x in late)/sum(x[1] for x in late) if late else 0

# ================= Excel =================
wb = openpyxl.Workbook()
HFILL = PatternFill('solid', fgColor='305496')
SUBFILL = PatternFill('solid', fgColor='8EAADB')
RED = PatternFill('solid', fgColor='FCE4E4')
GRN = PatternFill('solid', fgColor='E2EFDA')
TITLE = Font(bold=True, size=14, color='FFFFFF')
HFONT = Font(bold=True, color='FFFFFF')
BOLD = Font(bold=True)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
thin = Side(style='thin', color='BFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def hdr(ws, row, headers, fill=HFILL):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = HFONT; c.fill = fill; c.alignment = CENTER; c.border = BORDER


def put(ws, row, vals, numfmt=None):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=j, value=v)
        c.border = BORDER
        if numfmt and isinstance(v, (int, float)):
            c.number_format = numfmt


def setw(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ---- Sheet 1: 结论与口径 ----
ws = wb.active; ws.title = '结论与口径'
ws['A1'] = f'单用户功能使用 / 消费异常核查 · {EMAIL}（userid={UID}）'; ws['A1'].font = TITLE
ws['A1'].fill = HFILL; ws.merge_cells('A1:B1')
notes = [
    ('需求', '核查 maximefouquet33@gmail.com 的功能使用情况；背景是用户双语工单质疑 EPUB 翻译 token 消耗异常（Book B/C 每页≈A 的 2.6 倍），并提 5 问。'),
    ('规范大类', 'anomaly（单账号消费异常核查，镜像 T096/T097/T098 方法论）'),
    ('窗口', '2026-09-01 ~ 2026-11-04（首次用量 9/26，数据截至 11/02）'),
    ('主表 / 口径', 'immdata.token_used_aw（AW 账单），recordtype=capture，token=input+output；北京自然日；productline=功能维度'),
    ('总消耗', f'{pl_total/1e6:.1f}M token（{sum(x[1] for x in by_pl):,} 次扣费）'),
    ('功能结构（核心）', f'电子书(EPUB)翻译 占 {pct(by_pl[0][2], pl_total)}%（{by_pl[0][2]/1e6:.1f}M）—— 是绝对主力功能；网页翻译 {pct([x[2] for x in by_pl if x[0]=="web_page"][0], pl_total)}%、未归类 {pct(sum(x[2] for x in by_pl if x[0] in ("unknown","unknow")), pl_total)}%、字幕 {pct([x[2] for x in by_pl if x[0]=="subtitle_f"][0], pl_total)}%'),
    ('异常点（回应工单）', f'EPUB 单请求 input 从早期(Book A 期,9/27-10/03)≈{early_in:,.0f} token/请求，涨到近期书(10/31-11/02)≈{late_in:,.0f} token/请求——文本段长大 ~{late_in/early_in:.0f} 倍。这直接对应「后期书每页消耗更高」的现象，指向 EPUB 文本分组/分块方式已变化（工单 Q4）。'),
    ('Q1 怎么计 token', '账本记录上游返回的 input+output（按模型实计，无账本层系数）。自定义系统提示若被反复计入，应表现为固定大 input；但 EPUB 单请求 input 中位 538、p99≈7k、最大 10.7k，且无 >2 万的大请求——账本里看不到「系统提示被每条请求重复计入」的证据。'),
    ('Q2 有无按书明细', '账本无「book/task」维度字段（只有 productline/日期/模型/请求对）。可给「按天 × 功能 × 模型」明细（见各 sheet），但无法按具体哪本书拆——需翻译引擎侧日志按 book 关联。'),
    ('Q3 重试/续翻重复计', f'EPUB 全部 {epub_dup[0]:,} 条扣费中，(businessid,actionid) 全部唯一（重复对=0）→ 账本层面重试/失败的批次/续翻未被重复计费。'),
    ('Q4 近期计数/分组变化', '是：EPUB 单请求文本段大小在 9 月底→10 月持续变大（见「EPUB专项」sheet），后期书每页消耗的上涨与该分组变化一致。是否为 bug 需翻译引擎侧确认分块逻辑。'),
    ('Q5 多扣能否退', '本仓只读账本无法判定「多扣/应退」；但两点值得计费侧复核：① 用户 9/29 升 Max 年付（快照 AI 额度 50M），而订阅 AI 累计已用 ~99.6M（96.5M Pro 计数器 + 3.1M Max 计数器），远超 50M 名义额度；② 分块变大是否引入冗余。'),
    ('额度归属', '全部消耗来自订阅 AI 计数器（user_subs_ai_token_used_count_v2 96.5M + user_subs_max_ai_used_count 3.1M + DeepL 5.4M），未走任何购买的流量包（package）。'),
    ('排名基准', f'窗口内该用户以 {bench[2]/1e6:.1f}M token 排全量第 {bench[0]} 名 / {bench[1]:,} 活跃用户——极重度头部（前 {bench[0]/bench[1]*100:.4f}%）。'),
    ('局限（P043）', '只读账本只能证明消耗形态与分组变化；无法判定「是否被多扣」或「分块是否 bug」——需翻译引擎侧（EPUB 分块逻辑）与计费侧（额度上限/超量口径）确认。本仓无剩余额度/余额表。'),
]
r = 3
for k, v in notes:
    ws.cell(row=r, column=1, value=k).font = BOLD
    ws.cell(row=r, column=1).alignment = WRAP
    ws.cell(row=r, column=2, value=v).alignment = WRAP
    if k in ('异常点（回应工单）', 'Q4 近期计数/分组变化', 'Q5 多扣能否退'):
        ws.cell(row=r, column=1).fill = RED
    r += 1
setw(ws, [22, 104])

# ---- Sheet 2: 功能维度使用 ----
ws = wb.create_sheet('功能维度使用')
ws['A1'] = '功能维度（productline）使用分布'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:D1')
hdr(ws, 3, ['功能', '请求数', 'token', '占比%'])
r = 4
for pl, n, tok in by_pl:
    put(ws, r, [FEAT_CN.get(pl, pl), n, tok, pct(tok, pl_total)], '#,##0')
    r += 1
put(ws, r, ['合计', sum(x[1] for x in by_pl), pl_total, 100.0], '#,##0')
for j in range(1, 5):
    ws.cell(row=r, column=j).font = BOLD
# 高亮 EPUB
for rr in range(4, r):
    if ws.cell(row=rr, column=1).value and '电子书' in str(ws.cell(row=rr, column=1).value):
        for j in range(1, 5):
            ws.cell(row=rr, column=j).fill = RED
setw(ws, [20, 14, 18, 10])

# ---- Sheet 3: 每日×功能 矩阵 ----
ws = wb.create_sheet('每日×功能矩阵')
ws['A1'] = '每日 × 功能 token（北京自然日）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:E1')
# pivot
days = sorted(set(x[0] for x in day_pl))
pls = ['epub', 'web_page', 'subtitle_f', 'unknown', 'unknow', 'verify', 'text_page', 'comics']
pivot = {d: {p: 0 for p in pls} for d in days}
for d, p, tok in day_pl:
    pivot[d][p] = pivot[d].get(p, 0) + tok
hdr(ws, 3, ['北京日'] + [FEAT_CN.get(p, p) for p in pls] + ['当日合计'])
r = 4
for d in days:
    row = [d] + [pivot[d][p] for p in pls]
    row.append(sum(pivot[d].values()))
    put(ws, r, row, '#,##0')
    r += 1
setw(ws, [12] + [13]*len(pls) + [14])

# ---- Sheet 4: EPUB 专项（异常核心） ----
ws = wb.create_sheet('EPUB专项')
ws['A1'] = 'EPUB 电子书翻译专项 · 单请求 input 随时间变化（异常核心）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:F1')
hdr(ws, 3, ['北京日', '请求数', 'avg input', 'avg output', 'avg 总', 'max input'])
r = 4
for d, n, ain, aout, atot, maxin in epub_by_day:
    put(ws, r, [d, n, ain, aout, atot, maxin], '#,##0')
    # 标红单请求 input 偏大(>3000)的日期 = 分组变化后
    if ain and ain > 3000:
        for j in range(1, 7):
            ws.cell(row=r, column=j).fill = RED
    r += 1
r += 1
ws.cell(row=r, column=1, value='整体单请求分布').font = BOLD; r += 1
hdr(ws, r, ['指标', '值']); r += 1
for k, v in [('请求数', epub_stats[0]), ('avg input', round(epub_stats[1], 1)), ('avg output', round(epub_stats[2], 1)),
             ('max input', epub_stats[3]), ('median input', epub_stats[4]), ('p99 input', epub_stats[5])]:
    put(ws, r, [k, v], '#,##0'); r += 1
r += 1
ws.cell(row=r, column=1, value='早期(Book A 期 9/27-10/03) vs 近期书(10/31-11/02) 单请求 input 均值').font = BOLD; r += 1
hdr(ws, r, ['时段', '加权 avg input(请求)', '说明']); r += 1
put(ws, r, ['早期 9/27-10/03', round(early_in), 'Book A 期：文本段小，单请求 input 低']); r += 1
put(ws, r, ['近期 10/31-11/02', round(late_in), f'后期书：文本段长大 ~{late_in/early_in:.0f} 倍 → 每页消耗上涨的源头']); r += 1
for j in range(1, 4):
    ws.cell(row=r-1, column=j).fill = RED; ws.cell(row=r-2, column=j).fill = RED
setw(ws, [14, 12, 14, 14, 12, 12])

# ---- Sheet 5: EPUB 模型 与 输入分桶 ----
ws = wb.create_sheet('EPUB模型与输入分布')
ws['A1'] = 'EPUB 模型分布（actualresourceid）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:D1')
hdr(ws, 3, ['模型', 'provider', '请求数', 'token'])
r = 4
for m, prov, n, tok in epub_model:
    put(ws, r, [m, prov, n, tok], '#,##0'); r += 1
r += 1
ws.cell(row=r, column=1, value='EPUB input token 分桶（看是否有固定大 input=系统提示重复计入）').font = BOLD; r += 1
hdr(ws, r, ['区间', '请求数']); r += 1
for label, val in [('=0', epub_bkt[0]), ('1-1k', epub_bkt[1]), ('1k-5k', epub_bkt[2]), ('5k-20k', epub_bkt[3]), ('>20k', epub_bkt[4])]:
    put(ws, r, [label, val], '#,##0'); r += 1
r += 1
ws.cell(row=r, column=1, value='EPUB 重复计费检测 (businessid,actionid)').font = BOLD; r += 1
hdr(ws, r, ['检测项', '值', '结论']); r += 1
for k, v, note in [('扣费记录总数', epub_dup[0], ''), ('不同 (biz,act) 对数', epub_dup[1], ''),
                   ('重复对(>1次)', epub_dup[2], '=0 → 无重试/续翻重复计费'), ('单对最大重复', epub_dup[3], '=1 → 全唯一')]:
    put(ws, r, [k, v, note]); r += 1
setw(ws, [30, 14, 12, 14])

# ---- Sheet 6: 额度归属 ----
ws = wb.create_sheet('额度归属')
ws['A1'] = '额度归属（countername）—— 全部来自订阅，未走流量包'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:D1')
hdr(ws, 3, ['countername（计数器）', '含义', '请求数', 'token'])
r = 4
cntr_total = sum(x[2] for x in by_cntr)
for cn, n, tok in by_cntr:
    put(ws, r, [cn, CNTR_CN.get(cn, ''), n, tok], '#,##0'); r += 1
put(ws, r, ['合计', '', sum(x[1] for x in by_cntr), cntr_total], '#,##0')
for j in range(1, 5):
    ws.cell(row=r, column=j).font = BOLD
setw(ws, [40, 22, 12, 18])

# ---- Sheet 7: 按模型/Provider ----
ws = wb.create_sheet('按模型Provider')
ws['A1'] = '按模型 Provider 分布'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:C1')
hdr(ws, 3, ['providername', '请求数', 'token'])
r = 4
for p, n, tok in by_prov:
    put(ws, r, [p, n, tok], '#,##0'); r += 1
setw(ws, [20, 14, 18])

# ---- Sheet 8: 订阅与套餐 ----
ws = wb.create_sheet('订阅与套餐')
ws['A1'] = '订阅/套餐历史（imt_subscriptiongoodsorder）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:G1')
hdr(ws, 3, ['时间', '类型', '会员', '状态', '下单类型', '金额(分)', '天数'])
r = 4
for d, st, mem, os_, ot, ap, sd, snap in orders:
    put(ws, r, [d, st, mem, os_, ot, ap, sd], '#,##0'); r += 1
r += 1
ws.cell(row=r, column=1, value=f'注意：9/29 由 Pro 月付升级为 Max 年付（快照 OpenAITokenQuota=50000000=50M AI 额度）；但订阅 AI 累计已用~99.6M，远超 50M 名义额度，需计费侧复核额度上限/超量口径。').alignment = WRAP
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
setw(ws, [16, 16, 8, 10, 12, 10, 8])

# ---- Sheet 9: 排名基准 ----
ws = wb.create_sheet('排名基准')
ws['A1'] = '窗口内消耗量级排名'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL; ws.merge_cells('A1:B1')
hdr(ws, 3, ['指标', '值'])
r = 4
for k, v in [('本用户窗口 token', bench[2]), ('本用户排名', bench[0]), ('活跃用户总数', bench[1]),
             ('头部占比', f'前 {bench[0]/bench[1]*100:.4f}%'), ('窗口总 token', win_tot[1]), ('窗口活跃用户', win_tot[0])]:
    put(ws, r, [k, v], '#,##0'); r += 1
setw(ws, [22, 26])

OUT = 'output/user_token_maxime_20261103.xlsx'
import os
os.makedirs('output', exist_ok=True)
wb.save(OUT)
print('SAVED', OUT)
print('pl_total', pl_total, 'epub_share%', pct(by_pl[0][2], pl_total))
print('early_in', round(early_in), 'late_in', round(late_in), 'mult', round(late_in/early_in, 1))
print('epub dup', epub_dup, 'bench', bench)
print('cntr_total', cntr_total)
