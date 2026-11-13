# -*- coding: utf-8 -*-
"""重新交付 yupimelody24@gmail.com 额度消耗分析（基于 AW 账单 token_used_aw.countername 归属）。
回答三问：(1)流量包为何用得快 / 用户说只用了pro额度；(2)有无自动化嫌疑；(3)为何用AW账单。
"""
import sys, datetime, statistics
from collections import Counter
sys.path.insert(0, 'scripts')
from db import query
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

UID = 6515557
W0, W1 = '2026-10-22 00:00:00', '2026-10-31 00:00:00'
EMAIL = 'yupimelody24@gmail.com'
OUT = 'output/user_token_yupimelody_attr_20261030.xlsx'

def q(sql):
    cols, rows = query(sql)
    return cols, rows

# ---- 1) 订阅与套餐 ----
cols, orders = q(f"""SELECT to_char(createtime,'%Y-%m-%d %H:%M') d, subscriptiontype, membership,
  orderstatus, ordertype, amountpaid, subscriptionday,
  substring(subscriptiongoodssnap, position('OpenAITokenQuota' in subscriptiongoodssnap), 40) snap_quota
FROM immdata.imt_subscriptiongoodsorder
WHERE userid={UID} AND COALESCE(isdeleted,0)=0 ORDER BY createtime""")

# ---- 2) 10月按日 额度归属拆分 (subs vs package) ----
cols, oct_split = q(f"""SELECT to_char(timestamp,'%Y-%m-%d') day,
  sum(CASE WHEN countername='user_subs_ai_token_used_count_v2' THEN coalesce(inputusage,0)+coalesce(outputusage,0) ELSE 0 END) subs_ai,
  sum(CASE WHEN countername='user_ai_package_used_count' THEN coalesce(inputusage,0)+coalesce(outputusage,0) ELSE 0 END) pkg_ai,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) total,
  count(*) n
FROM immdata.token_used_aw
WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='2026-10-01' AND timestamp<'2026-11-01' GROUP BY 1 ORDER BY 1""")

# ---- 3) 窗口内 按 countername ----
cols, win_counter = q(f"""SELECT countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw
WHERE userid={UID} AND recordtype='capture' AND timestamp>='{W0}' AND timestamp<'{W1}'
GROUP BY 1 ORDER BY tok DESC""")

# ---- 4) 窗口每日消耗（按日） ----
cols, daily = q(f"""SELECT to_char(timestamp,'%Y-%m-%d') day, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw
WHERE userid={UID} AND recordtype='capture' AND timestamp>='{W0}' AND timestamp<'{W1}'
GROUP BY 1 ORDER BY 1""")

# ---- 5) 按模型 ----
cols, bymodel = q(f"""SELECT providername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw
WHERE userid={UID} AND recordtype='capture' AND timestamp>='{W0}' AND timestamp<'{W1}'
GROUP BY 1 ORDER BY tok DESC""")

# ---- 6) 时段分布（小时） ----
cols, hourly = q(f"""SELECT to_char(timestamp,'%H') hr, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw
WHERE userid={UID} AND recordtype='capture' AND timestamp>='{W0}' AND timestamp<'{W1}'
GROUP BY 1 ORDER BY 1""")

# ---- 7) 排名基准（AW账单口径） ----
cols, rank_r = q(f"""WITH u AS (
  SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
  FROM immdata.token_used_aw WHERE timestamp>='{W0}' AND timestamp<'{W1}' AND recordtype='capture'
  GROUP BY 1)
SELECT (SELECT count(*) FROM u WHERE tok>=(SELECT tok FROM u WHERE userid={UID})) rank_no,
       (SELECT count(*) FROM u) total_users,
       (SELECT tok FROM u WHERE userid={UID}) this_tok""")

# ---- 8) 自动化：原始时间戳 -> 间隔/突发 ----
cols, tsrows = q(f"""SELECT to_char(timestamp,'%Y-%m-%d %H:%M:%S') ts
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
AND timestamp>='{W0}' AND timestamp<'{W1}' ORDER BY timestamp""")
ts = [datetime.datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S') for r in tsrows]
gaps = [(ts[i+1]-ts[i]).total_seconds() for i in range(len(ts)-1)]
gaps_s = sorted(gaps)
def pct(p): return gaps_s[min(len(gaps_s)-1, int(len(gaps_s)*p))]
bymin = Counter(t.replace(second=0) for t in ts)
permin = sorted(bymin.values())
sub1 = sum(1 for g in gaps if g < 1)
g15 = sum(1 for g in gaps if 1 <= g < 5)
g560 = sum(1 for g in gaps if 5 <= g < 60)
g60 = sum(1 for g in gaps if g >= 60)
devices = q(f"""SELECT deviceid, count(*) n, min(to_char(installtime,'%Y-%m-%d')) inst
FROM immdata.imt_deviceinfo WHERE userid={UID} GROUP BY 1 ORDER BY n DESC""")
ub = q(f"""SELECT count(*) events, count(DISTINCT device_id) dev, count(DISTINCT browser_name) br,
  count(DISTINCT os_name) os, max(browser_name) br_max, max(os_name) os_max, max(translation_mode) mode
FROM immdata.user_behaviour
WHERE device_id IN (SELECT deviceid FROM immdata.imt_deviceinfo WHERE userid={UID})
  AND created_ts>='{W0}' AND created_ts<'{W1}'""")

# ============ 写 Excel ============
wb = openpyxl.Workbook()
H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='305496')
TITLE = Font(bold=True, size=13); BOLD = Font(bold=True)
thin = Side(style='thin', color='D0D0D0'); BORD = Border(thin, thin, thin, thin)
WRAP = Alignment(wrap_text=True, vertical='top')
RED = PatternFill('solid', fgColor='FCE4E4'); GRN = PatternFill('solid', fgColor='E2EFDA')

def hdr(ws, row, headers):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row, j, h); c.font = H; c.fill = HF; c.border = BORD
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

def put(ws, r, vals):
    for j, v in enumerate(vals, 1):
        c = ws.cell(r, j, v); c.border = BORD
        if isinstance(v, float): c.number_format = '#,##0'

# Sheet 1: 结论与口径
ws = wb.active; ws.title = '结论与口径'
ws['A1'] = f'用户 {EMAIL}（userid={UID}）额度消耗分析 — 基于 AW 账单 token_used_aw'; ws['A1'].font = TITLE
rows = [
 ('问题', '结论'),
 ('① 流量包为何用得快 / 用户说“只用了 Pro 额度”',
  'AW 账单 countername 显示：10/22–10/30 窗口内 100% 的 AI 消耗（9.60M token）记在“买的流量包”'
  '（user_ai_package_used_count），Pro 月额度计数器（user_subs_ai_token_used_count_v2）在该窗口 0 条。'
  '用户的“只用了 Pro 额度”与账本不符——窗口里实际走的是流量包。'),
 ('根因',
  'Pro 月额度计数器 6/26–10/20 一直有量（全期 77.9M，仅 10/02–10/20 就 19.9M），10/20 当天起突然静默、'
  '改走流量包。订阅本身 10/02 已 finished 续费（¥15/31天，覆盖到 ~11/02），故非订阅过期，而是该账号 AI 额度'
  '约在 10/20 被耗尽、回退到已购流量包。全局 Pro 计数器 10/20 前后稳定（无系统性切换），故为账号级额度耗尽，非计费故障。'),
 ('消耗量级',
  '窗口日均 ~1.2M token、8 天连发。单包（订单快照 OpenAITokenQuota=10,000,000；注意类型名写“500w”但快照为 10M，需计费确认）'
  '按此速率约 8 天抽干 → 故“用得快”。'),
 ('② 有无自动化嫌疑',
  '不像分布式机器人：仅 3 个设备、Safari/macOS、翻译模式、有夜间长间隙（p99 间隔 19 分钟、最大 24 小时）。'
  '但频率确实高：请求间隔中位数 2s、15.6% 为亚秒级突发、峰值 74 请求/分钟——更像重度人工翻译 / 翻译工作流'
  '（如整页/整文档分段翻、CAT 或轻度 API 工作流）。非滥用，但高频本身就是消耗快的直接原因。'),
 ('③ 为何用 AW 账单',
  '上版用 imm_token_used（日汇总，无额度归属列）作主力、仅从 token_used_aw 取了金额，漏看了 countername 归属列。'
  'token_used_aw 即 AW 账单（billing-ledger 落表），其 countername 正是回答“扣的是 Pro 还是流量包”的权威字段，本版以它为准。'),
 ('局限',
  '只读仓无“剩余额度/余额”表，确切 Pro AI 额度上限与 10/20 切换阈值需计费侧确认（名义 5M 与实测 ~19.9M 不符，疑似快照字段偏低或额度更高）。'
  '“人 vs 轻度自动化”需请求内容/会话关联，本仓账本无，未定性。'),
]
r = 3; hdr(ws, r, ['问题', '结论']); r += 1
for a, b in rows[1:]:
    ws.cell(r, 1, a).border = BORD; ws.cell(r, 1).alignment = WRAP; ws.cell(r, 1).font = BOLD
    ws.cell(r, 2, b).border = BORD; ws.cell(r, 2).alignment = WRAP
    fill = RED if '流量包' in a or '自动化' in a else None
    r += 1
ws.column_dimensions['A'].width = 26; ws.column_dimensions['B'].width = 95

# Sheet 2: 额度归属_按日（10月）
ws = wb.create_sheet('额度归属_按日(10月)')
ws['A1'] = '10 月按日 额度归属拆分（AW 账单 countername）'; ws['A1'].font = TITLE
ws['A2'] = 'subs_ai=Pro月额度计数器；pkg_ai=买的流量包计数器；切换点在 10/20'; ws['A2'].font = Font(italic=True, color='808080')
hdr(ws, 4, ['日期', 'Pro月额度(token)', '流量包(token)', '合计(token)', '记录数', '主要归属'])
r = 5
for d, sa, pa, tot, n in oct_split:
    main = 'Pro月额度' if sa >= pa else ('流量包' if pa > 0 else 'Pro月额度')
    put(ws, r, [d, sa, pa, tot, n, main])
    if pa > 0 and sa == 0:
        for j in range(1, 7): ws.cell(r, j).fill = RED
    r += 1
for col, w in zip('ABCDEF', [12, 18, 16, 16, 10, 12]): ws.column_dimensions[col].width = w

# Sheet 3: 窗口归属
ws = wb.create_sheet('窗口归属_10-22_10-30')
ws['A1'] = '窗口 10/22–10/30 按 countername（额度归属）'; ws['A1'].font = TITLE
hdr(ws, 3, ['countername（计数器）', '含义', '记录数', 'token'])
mean = {'user_ai_package_used_count': '买的 AI 流量包', 'user_deepl_package_used_count': '买的 DeepL 流量包',
        'user_subs_ai_token_used_count_v2': 'Pro 月订阅 AI 额度', 'user_subs_deep_l_used_count_v2': 'Pro 月订阅 DeepL 额度'}
r = 4
for cn, n, tok in win_counter:
    put(ws, r, [cn, mean.get(cn, ''), n, tok])
    if 'package' in cn: 
        for j in range(1,5): ws.cell(r,j).fill = RED
    r += 1
for col, w in zip('ABCD', [38, 22, 12, 16]): ws.column_dimensions[col].width = w

# Sheet 4: 每日消耗
ws = wb.create_sheet('每日消耗')
hdr(ws, 1, ['日期', '记录数', 'token'])
for i, (d, n, tok) in enumerate(daily, 2): put(ws, i, [d, n, tok])
for col, w in zip('ABC', [14, 12, 16]): ws.column_dimensions[col].width = w

# Sheet 5: 按模型
ws = wb.create_sheet('按模型')
hdr(ws, 1, ['provider', '记录数', 'token'])
for i, (p, n, tok) in enumerate(bymodel, 2): put(ws, i, [p, n, tok])
for col, w in zip('ABC', [20, 12, 16]): ws.column_dimensions[col].width = w

# Sheet 6: 时段分布
ws = wb.create_sheet('时段分布')
hdr(ws, 1, ['小时', '记录数', 'token'])
for i, (h, n, tok) in enumerate(hourly, 2): put(ws, i, [int(h), n, tok])
for col, w in zip('ABC', [10, 12, 16]): ws.column_dimensions[col].width = w

# Sheet 7: 自动化嫌疑
ws = wb.create_sheet('自动化嫌疑')
ws['A1'] = '自动化/高频 时序指标（窗口）'; ws['A1'].font = TITLE
metrics = [
 ('总记录数', len(ts)),
 ('活跃分钟数', len(permin)),
 ('请求间隔 中位数(s)', round(statistics.median(gaps), 1)),
 ('请求间隔 均值(s)', round(statistics.mean(gaps), 1)),
 ('p90(s)', pct(0.90)), ('p95(s)', pct(0.95)), ('p99(s)', pct(0.99)), ('最大间隔(s)', max(gaps)),
 ('亚秒级间隔数(<1s)', sub1), ('1-5s 间隔数', g15), ('5-60s 间隔数', g560), ('>60s 间隔数', g60),
 ('峰值 请求/分钟', max(permin)), ('p99 请求/分钟', permin[int(len(permin)*0.99)]), ('中位数 请求/分钟', statistics.median(permin)),
 ('≥30请求/分钟 的分钟数', sum(1 for v in permin if v >= 30)),
 ('≥60请求/分钟 的分钟数', sum(1 for v in permin if v >= 60)),
]
hdr(ws, 3, ['指标', '值'])
r = 4
for k, v in metrics:
    ws.cell(r, 1, k).border = BORD; ws.cell(r, 2, v).border = BORD
    if '亚秒' in k and v: ws.cell(r,2).fill = RED
    r += 1
r += 1
ws.cell(r, 1, '设备/UA（user_behaviour + deviceinfo）').font = BOLD; r += 1
ue = ub[1][0] if ub[1] else None
if ue:
    for label, val in [('行为事件数', ue[0]), ('设备数', ue[1]), ('浏览器数', ue[2]), ('OS数', ue[3]),
                       ('主浏览器', ue[4]), ('主OS', ue[5]), ('翻译模式', ue[6])]:
        ws.cell(r, 1, label).border = BORD; ws.cell(r, 2, val).border = BORD; r += 1
r += 1
ws.cell(r, 1, 'deviceinfo 设备清单').font = BOLD; r += 1
hdr(ws, r, ['device_id', '记录数', '安装日']); r += 1
for did, n, inst in devices[1]:
    put(ws, r, [did[:24]+'…' if len(did) > 24 else did, n, inst]); r += 1
for col, w in zip('ABC', [40, 14, 14]): ws.column_dimensions[col].width = w

# Sheet 8: 订阅与套餐
ws = wb.create_sheet('订阅与套餐')
ws['A1'] = '订阅/套餐历史（imt_subscriptiongoodsorder）'; ws['A1'].font = TITLE
hdr(ws, 3, ['购买时间', '类型', '会员', '状态', '下单类型', '金额', '天数', '快照AI额度字段'])
r = 4
for d, st, mem, os_, ot, ap, sd, snap in orders:
    put(ws, r, [d, st, mem, os_, ot, ap, sd, snap])
    if 'package' in st:
        for j in range(1, 9): ws.cell(r, j).fill = RED
    r += 1
for col, w in zip('ABCDEFGH', [16, 22, 8, 10, 14, 8, 8, 40]): ws.column_dimensions[col].width = w

# Sheet 9: 排名基准
ws = wb.create_sheet('排名基准')
ws['A1'] = '窗口内消耗量级排名（AW 账单口径）'; ws['A1'].font = TITLE
rkrows = rank_r[1] if isinstance(rank_r, tuple) and len(rank_r) > 1 else rank_r
rr = rkrows[0] if (rkrows and len(rkrows) > 0) else (None, None, None)
hdr(ws, 3, ['本用户排名', '活跃用户总数', '本用户窗口 token'])
put(ws, 4, list(rr))
ws.column_dimensions['A'].width = 16; ws.column_dimensions['B'].width = 16; ws.column_dimensions['C'].width = 18

wb.save(OUT)
print('SAVED', OUT)
print('rank', rr)
print('window total tok (AW)', sum(t for _,_,t in win_counter))
print('oct pkg total', sum(p for _,_,p,_,_ in oct_split))
print('inter-arrival median/sub1/p99', statistics.median(gaps), sub1, pct(0.99))
