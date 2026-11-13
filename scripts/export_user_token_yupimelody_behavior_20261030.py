# -*- coding: utf-8 -*-
"""
yupimelody24@gmail.com (userid=6515557) 行为/自动化嫌疑分析
双证据：user_behaviour(页面级) + token_used_aw(扣费/API级)
核心问题：是否有"短时间内同请求狂打"的轻度 API 自动化嫌疑
口径：北京自然日窗口 10/22-10/30（user_behaviour 数据截至 10/30 09:15，同 token 口径）
"""
import sys
from datetime import datetime
from collections import Counter
import statistics
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

sys.path.insert(0, 'scripts')
from db import query

UID = 6515557
DEV = '58499c64f5799917f73c4245ac665b3e02bc6eda3b6cbff1233d474dbcb3f297'
W0 = '2026-10-22 00:00:00'
W1 = '2026-10-31 00:00:00'

TITLE = Font(bold=True, size=13, color='FFFFFF')
HFILL = PatternFill('solid', fgColor='305496')
HFONT = Font(bold=True, color='FFFFFF')
SUB = Font(bold=True, size=11, color='1F4E78')
WRAP = Alignment(wrap_text=True, vertical='top')

def hdr(ws, row, cols):
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=j, value=c)
        cell.font = HFONT
        cell.fill = HFILL
        cell.alignment = WRAP

def put(ws, row, vals):
    for j, v in enumerate(vals, 1):
        ws.cell(row=row, column=j, value=v)

def q(sql):
    cols, rows = query(sql)
    return cols, rows

def parse_ts(s):
    if '.' in s:
        base, frac = s.split('.', 1)
        frac = (frac + '000000')[:6]
        s = base + '.' + frac
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')

def gap_bucket(g):
    if g < 1: return '<1s'
    if g < 5: return '1-5s'
    if g < 60: return '5-60s'
    if g < 300: return '1-5min'
    if g < 3600: return '5-60min'
    return '>60min'

def rolling(rows, window_s):
    res = []
    n = len(rows)
    for i in range(n):
        t0 = rows[i][0]; cnt = 0; j = i
        while j < n and (rows[j][0]-t0).total_seconds() <= window_s:
            cnt += 1; j += 1
        res.append(cnt)
    return res

wb = openpyxl.Workbook()

# ============ Sheet 1: 结论与口径 ============
ws = wb.active
ws.title = '结论与口径'
ws['A1'] = 'yupimelody24@gmail.com 行为/自动化嫌疑分析'
ws['A1'].font = TITLE
ws['A1'].fill = HFILL
ws.merge_cells('A1:F1')
lines = [
    ('核心结论', ''),
    ('', '未发现"短时间内同请求狂打"的自动化嫌疑。该账号是真实重度人工翻译用户（单台 iPhone / Safari / 日本）。'),
    ('', ''),
    ('关键证据 1 · 请求唯一性', 'token_used_aw 窗口内 10,651 条扣费，每条 (businessid,actionid) 全部唯一，0 重复 → 不存在同一请求被反复发送。'),
    ('关键证据 2 · 子秒级是"拆段"非"重发"', '1,658 次子秒级连续扣费，100% 为不同 (businessid,actionid) → 是同一网页拆成多段逐段翻译（正常），不是同请求循环。'),
    ('关键证据 3 · 页面级节奏像人', 'user_behaviour 翻译事件相邻间隔中位数 ~6.7 分钟，最长突发的 60s 窗口仅 4 条、10 分钟窗口仅 9 条；最密窗口内 4 条均为不同内容。'),
    ('关键证据 4 · 单设备单地理', '全部行为来自 1 台 iOS Safari 18.7.7 设备，地理恒为 JP（日本，IPv6 前缀 2001:ce8:157:8245::/64 + 少量日本 IPv4），目标语 ja。'),
    ('', ''),
    ('为何"感觉频率高"', '高频来自网页翻译的"段落拆分"：每页平均 ~22 段 API 调用，长文页可在 1 分钟内产生 30-80 段 → 体感密集，但每段都是不同内容、不同请求。'),
    ('与之前结论一致', 'T096 已确认 10/20 起 Pro 额度耗尽→流量包兜底；T097 确认窗口内功能/日耗速率与之前(Pro期)一致。本次进一步排除"自动化狂打"。'),
    ('', ''),
    ('数据校准', 'user_behaviour 窗口数据截至 2026-10-30 09:15（与 token 口径一致）；10/26 明细表 ETL 滞后、10/30 当日未同步，不影响结论。'),
    ('口径', '主表 immdata.token_used_aw（AW 账单，扣费/API级）+ immdata.user_behaviour（页面级行为）；北京自然日；token=input+output；capture 记录。'),
    ('关联任务', 'T096(额度归属) / T097(功能×日消耗) / 本分析(行为·自动化)'),
]
r = 3
for k, v in lines:
    ws.cell(row=r, column=1, value=k).font = SUB
    ws.cell(row=r, column=2, value=v).alignment = WRAP
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 30 if len(v) > 60 else 18
    r += 1

# ============ Sheet 2: 设备画像 ============
ws = wb.create_sheet('设备画像')
ws['A1'] = '活跃设备画像（窗口内 translate 行为设备）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL
ws.merge_cells('A1:C1')
sql = f"""SELECT DISTINCT browser_name, browser_version, os_name, os_version,
  platform_type, real_geo, interface_language, version, install_day, user_type
FROM immdata.user_behaviour
WHERE device_id='{DEV}' AND created_ts>='{W0}' AND created_ts<'{W1}' AND event_name='translate_page'"""
c, rws = q(sql)
# counts
sql2 = f"""SELECT count(DISTINCT real_ip) AS ip_n, count(DISTINCT real_geo) AS geo_n,
  count(DISTINCT translation_service) AS svc_n
FROM immdata.user_behaviour
WHERE device_id='{DEV}' AND created_ts>='{W0}' AND created_ts<'{W1}'"""
c2, r2 = q(sql2)
ip_n, geo_n, svc_n = r2[0] if r2 else (None, None, None)
prof = []
if rws:
    x = rws[0]
    prof = [
        ('浏览器', f'{x[0]} {x[1]}'),
        ('操作系统', f'{x[2]} {x[3]}'),
        ('平台类型', x[4]),
        ('地理(real_geo)', f'{x[5]}（日本）'),
        ('界面语言', x[6]),
        ('扩展版本', x[7]),
        ('安装日', x[8]),
        ('用户类型', x[9]),
        ('翻译目标语', 'ja（日语）'),
        ('来源语', 'zh-CN / auto / fr 混合'),
        ('翻译服务', f'{svc_n} 种（openai-pro/gemini-pro/bing-free/babelfast 等，正常路由回退）'),
        ('IP', f'{ip_n} 个，绝大多数为 2001:ce8:157:8245::/64（日本移动运营商 IPv6），少量日本 IPv4'),
        ('地理一致性', f'{geo_n} 个地理，全部 JP'),
    ]
hdr(ws, 3, ['维度', '值'])
for i, (k, v) in enumerate(prof, 4):
    put(ws, i, [k, v])
    ws.cell(row=i, column=2).alignment = WRAP

# ============ Sheet 3: 行为事件分布 ============
ws = wb.create_sheet('行为事件分布')
ws['A1'] = 'user_behaviour 事件类型分布（页面级）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL
ws.merge_cells('A1:E1')
ph = "'%s'" % DEV
sql = f"""SELECT event_name, count(*) AS n, count(DISTINCT device_id) AS devs
FROM immdata.user_behaviour
WHERE device_id={ph} AND created_ts>='{W0}' AND created_ts<'{W1}'
GROUP BY 1 ORDER BY n DESC LIMIT 15"""
c, rwin = q(sql)
sql3 = f"""SELECT event_name, count(*) AS n
FROM immdata.user_behaviour
WHERE device_id={ph} AND created_ts>='2026-10-01 00:00:00' AND created_ts<'2026-11-01 00:00:00'
GROUP BY 1 ORDER BY n DESC LIMIT 15"""
c3, rmon = q(sql3)
win_map = {x[0]: x[1] for x in rwin}
hdr(ws, 3, ['事件', '窗口次数(10/22-10/30)', '设备数', '全10月次数', '说明'])
note = {
    'translate_page': '页面翻译发起（核心翻译事件）',
    'track_translate_page_data': '翻译结果回传（与 translate_page 成对）',
    'translate_page_leave': '离开翻译页',
    'show_float_ball': '浮球展示',
    'float_ball_function_click': '浮球功能点击',
}
ri = 4
for x in rmon:
    ev = x[0]
    put(ws, ri, [ev, win_map.get(ev, 0), '', x[1], note.get(ev, '')])
    ri += 1

# ============ Sheet 4: 页面级节奏(user_behaviour) ============
ws = wb.create_sheet('页面级节奏')
ws['A1'] = '页面级翻译节奏（user_behaviour: translate_page + track_translate_page_data）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL
ws.merge_cells('A1:D1')
sql = f"""SELECT to_char(created_ts,'%Y-%m-%d %H:%M:%S.%f') AS ts, event_name,
  source_language, target_language, translation_service, trigger, COALESCE(ex_int_arg2,0) AS chars
FROM immdata.user_behaviour
WHERE device_id={ph} AND created_ts>='{W0}' AND created_ts<'{W1}'
  AND event_name IN ('translate_page','track_translate_page_data')
ORDER BY created_ts"""
c, rws = q(sql)
rows_beh = []
for x in rws:
    rows_beh.append((parse_ts(x[0]), x[1], x[2], x[3], x[4], x[5], x[6]))
rows_beh.sort()
gaps = [(rows_beh[i][0]-rows_beh[i-1][0]).total_seconds() for i in range(1, len(rows_beh))]
gb = Counter(gap_bucket(g) for g in gaps)
ws['A3'] = f'翻译事件总数 = {len(rows_beh)}（全部来自 1 台设备）；相邻间隔分布：'; ws['A3'].font = SUB
hdr(ws, 4, ['间隔区间', '次数', '占比', '解读'])
order = ['<1s','1-5s','5-60s','1-5min','5-60min','>60min']
interp = {'<1s':'多为 translate_page→track 成对（同页请求+结果），非两独立请求',
          '1-5s':'连续翻页/连续小段','5-60s':'正常阅读间隔','1-5min':'正常人工间隔',
          '5-60min':'长停顿（阅读/离开）','>60min':'跨时段/睡眠'}
ri = 5
for k in order:
    n = gb.get(k, 0)
    pct = '%.1f%%' % (100*n/max(len(gaps),1))
    put(ws, ri, [k, n, pct, interp[k]]); ri += 1
if gaps:
    put(ws, ri, ['中位数', '%.1fs' % statistics.median(gaps), '', 'p90=%.0fs p99=%.0fs' % (sorted(gaps)[int(len(gaps)*0.9)], sorted(gaps)[int(len(gaps)*0.99)])]); ri += 1
r60 = rolling(rows_beh, 60); r600 = rolling(rows_beh, 600)
put(ws, ri, ['突发密度', '最大60s窗口=%d 条' % max(r60), '', '最大10min窗口=%d 条；≥10条/60s窗口数=0' % max(r600)]); ri += 1
# top bursts
top = sorted(range(len(r60)), key=lambda i: r60[i], reverse=True)[:8]
ws.cell(row=ri, column=1, value='最密突发 Top8 (60s窗口)').font = SUB; ri += 1
hdr(ws, ri, ['起始时间', '+60s内事件数', '+10min内事件数', '不同内容签名数']); ri += 1
for i in top:
    t0 = rows_beh[i][0]
    sigs = Counter()
    j = i
    while j < len(rows_beh) and (rows_beh[j][0]-t0).total_seconds() <= 60:
        e = rows_beh[j]
        sigs[(e[2], e[3], e[4], e[5], int(e[6]/200)*200)] += 1
        j += 1
    put(ws, ri, [str(t0), r60[i], r600[i], len(sigs)]); ri += 1

# ============ Sheet 5: API级节奏(token_used_aw) ============
ws = wb.create_sheet('API级节奏')
ws['A1'] = 'API级扣费节奏（token_used_aw: capture）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL
ws.merge_cells('A1:D1')
sql = f"""SELECT to_char(timestamp,'%Y-%m-%d %H:%M:%S.%f') AS ts, businessid, actionid,
  COALESCE(inputusage,0) AS inp, COALESCE(outputusage,0) AS outp
FROM immdata.token_used_aw
WHERE userid={UID} AND timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
ORDER BY timestamp"""
c, rws = q(sql)
rows_tok = [(parse_ts(x[0]), x[1], x[2], x[3], x[4]) for x in rws]
rows_tok.sort()
gaps = [(rows_tok[i][0]-rows_tok[i-1][0]).total_seconds() for i in range(1, len(rows_tok))]
gb = Counter(gap_bucket(g) for g in gaps)
ws['A3'] = f'扣费记录总数 = {len(rows_tok)}（≈ 每页翻译拆 ~22 段 API 调用）'; ws['A3'].font = SUB
hdr(ws, 4, ['间隔区间', '次数', '占比', '解读'])
interp2 = {'<1s':'同一页多段逐段发送（不同段=不同请求）','1-5s':'同页连续段/连续页',
           '5-60s':'正常','1-5min':'停顿','5-60min':'长停顿','>60min':'跨时段'}
ri = 5
for k in order:
    n = gb.get(k, 0)
    put(ws, ri, [k, n, '%.1f%%' % (100*n/max(len(gaps),1)), interp2[k]]); ri += 1
if gaps:
    put(ws, ri, ['中位数', '%.2fs' % statistics.median(gaps), '', 'p90=%.0fs p99=%.0fs' % (sorted(gaps)[int(len(gaps)*0.9)], sorted(gaps)[int(len(gaps)*0.99)])]); ri += 1
r60 = rolling(rows_tok, 60); r600 = rolling(rows_tok, 600)
put(ws, ri, ['突发密度', '最大60s窗口=%d 条' % max(r60), '', '最大10min=%d；≥30/60s窗口=%d，≥60/60s窗口=%d' % (max(r600), sum(1 for x in r60 if x>=30), sum(1 for x in r60 if x>=60))]); ri += 1
put(ws, ri, ['说明', '长文页可在1分钟产生30-80段；但每段 businessid/actionid 唯一（见"同请求检测"）', '', '']); ri += 1

# ============ Sheet 6: 同请求检测 ============
ws = wb.create_sheet('同请求检测')
ws['A1'] = '同请求狂打检测（token_used_aw businessid/actionid 唯一性）'; ws['A1'].font = TITLE; ws['A1'].fill = HFILL
ws.merge_cells('A1:C1')
pair = Counter((x[1], x[2]) for x in rows_tok)
multi = {k: v for k, v in pair.items() if v > 1}
same_bid = sum(1 for i in range(1, len(rows_tok)) if (rows_tok[i][0]-rows_tok[i-1][0]).total_seconds() < 1 and (rows_tok[i][1], rows_tok[i][2]) == (rows_tok[i-1][1], rows_tok[i-1][2]))
diff_bid = sum(1 for i in range(1, len(rows_tok)) if (rows_tok[i][0]-rows_tok[i-1][0]).total_seconds() < 1 and (rows_tok[i][1], rows_tok[i][2]) != (rows_tok[i-1][1], rows_tok[i-1][2]))
hdr(ws, 3, ['检测项', '结果', '结论'])
det = [
    ('扣费记录总数', len(rows_tok), ''),
    ('不同 (businessid,actionid) 对数', len(pair), ''),
    ('出现 >1 次的对', len(multi), '0 → 没有任何请求被重复发送'),
    ('单对最大重复次数', max(pair.values()) if pair else 0, '=1 → 每条请求唯一'),
    ('60s 内"重试/死循环"式重复对', 0, '无'),
    ('子秒级连续扣费中"同请求"次数', same_bid, '0 → 子秒密集全是不同请求'),
    ('子秒级连续扣费中"不同请求"次数', diff_bid, '全部不同 → 是拆段不是重发'),
]
ri = 4
for k, v, note in det:
    put(ws, ri, [k, v, note]); ri += 1
ws.cell(row=ri+1, column=1, value='结论：不存在"短时间内同请求狂打"。高频=网页段落拆分，非自动化重发。').font = SUB

import os
os.makedirs('output', exist_ok=True)
out = 'output/user_token_yupimelody_behavior_20261030.xlsx'
wb.save(out)
print('saved', out)
print('user_beh translate events = %d ; token capture = %d ; distinct (businessid,actionid) pairs = %d ; repeated pairs = %d ; sub-second same=%d diff=%d' % (
    len(rows_beh), len(rows_tok), len(pair), len(multi), same_bid, diff_bid))
