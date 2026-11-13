"""T107f: among SG/MY-attributed PAYING users who paid in CNY,
how many have Simplified-Chinese (zh-CN) as their dominant translation
target language? (VPN-proxy: real Chinese users whose IP shows SG/MY.)

Same attribution as T107b/T107e:
  paid orders -> user -> device -> imm_regional_activation
  - dominant real_geo  = region (SG / MY)
  - dominant target_language = "usual" translation language
One heavy scan over imm_regional_activation (group by userid, real_geo,
target_language), then derive both dominant geo and dominant lang in Python.

Window: current year 2025-11 .. 2026-11 (Beijing), finished paid orders.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query

OUT = Path("output/sg_my_revenue")
OUT.mkdir(parents=True, exist_ok=True)

def q(sql, retries=6):
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i+1} ({d:.0f}s): {e}")
            time.sleep(d); d *= 2

CTES = """
WITH paid AS (
  SELECT userid, UPPER(currency) AS cur, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
         OR subscriptiontype LIKE 'onetime%')
    AND createtime >= TIMESTAMP '2025-11-01 00:00:00'
    AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
),
paying_users AS (SELECT DISTINCT userid FROM paid),
ud AS (
  SELECT d.userid, d.deviceid
  FROM immdata.imt_deviceinfo d
  WHERE COALESCE(d.isdeleted,0)=0
    AND d.userid IN (SELECT userid FROM paying_users)
),
ug3 AS (
  SELECT ud.userid, a.real_geo, a.target_language, COUNT(*) AS cnt
  FROM ud JOIN immdata.imm_regional_activation a
    ON a.device_id = ud.deviceid
   AND a.created_ts >= DATE '2020-01-01' AND a.created_ts <= DATE '2026-12-31'
  GROUP BY ud.userid, a.real_geo, a.target_language
)
"""

print("== running activation scan (geo + target_language per user) ==")
cols, rows = q(CTES + "SELECT userid, real_geo, target_language, cnt FROM ug3")
print("rows:", len(rows))

from collections import defaultdict
# per-user: geo counts, lang counts
geo_cnt = defaultdict(lambda: defaultdict(int))
lang_cnt = defaultdict(lambda: defaultdict(int))
for uid, geo, lang, cnt in rows:
    if uid is None:
        continue
    if geo is not None:
        geo_cnt[uid][geo] += cnt
    if lang is not None:
        lang_cnt[uid][lang] += cnt

def dominant(d):
    if not d:
        return None
    return max(d.items(), key=lambda x: x[1])[0]

user_geo = {u: dominant(g) for u, g in geo_cnt.items()}
user_lang = {u: dominant(l) for u, l in lang_cnt.items()}

# orders -> per-user currency set (does this user ever pay in CNY?)
print("== running order currency scan ==")
_, orows = q("""
SELECT userid, UPPER(currency)
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0
  AND orderstatus='finished'
  AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
       OR subscriptiontype LIKE 'onetime%')
  AND createtime >= TIMESTAMP '2025-11-01 00:00:00'
  AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
""")
user_cur = defaultdict(set)
for uid, cur in orows:
    if uid is None:
        continue
    user_cur[uid].add(cur)

# ---- assemble: SG/MY-attributed CNY payers ----
def analyze(geo_filter):
    # returns dict lang -> set of users (distinct)
    lang_users = defaultdict(set)
    cn_users = set()
    for u, g in user_geo.items():
        if g not in geo_filter:
            continue
        if "CNY" not in user_cur.get(u, set()):
            continue
        cn_users.add(u)
        lang_users[user_lang.get(u, "NULL")].add(u)
    return lang_users, cn_users

print("\n=== CNY 付费的 SG/MY 用户: 主导翻译语言分布 ===")
result = {}
for region, gf in [("SG", {"SG"}), ("MY", {"MY"}), ("SG+MY", {"SG","MY"})]:
    lang_users, cn_users = analyze(gf)
    total = len(cn_users)
    zh = len(lang_users.get("zh-CN", set()))
    result[region] = {"total": total, "zh": zh, "lang_users": lang_users}
    print(f"\n[{region}] CNY 付费用户总数 = {total:,}")
    print(f"  其中主导翻译语言 = zh-CN (简中) 的人数 = {zh:,}  (占比 {zh/total*100:.1f}%)")
    print("  全部主导翻译语言分布 (top 12):")
    for lang, us in sorted(lang_users.items(), key=lambda x:-len(x[1]))[:12]:
        print(f"    {str(lang):<12} {len(us):>7,} 人  ({len(us)/total*100:4.1f}%)")

# comparison: non-CNY payers in SG/MY (SGD/MYR/USD etc.) zh-CN share
print("\n=== 对照: 非 CNY 付费的 SG/MY 用户 zh-CN 占比 (看 VPN 信号是否 CNY 专属) ===")
def analyze_non_cny(gf):
    lang_users = defaultdict(set)
    users = set()
    for u, g in user_geo.items():
        if g not in gf:
            continue
        cur = user_cur.get(u, set())
        if "CNY" in cur:
            continue
        if not cur:
            continue
        users.add(u)
        lang_users[user_lang.get(u, "NULL")].add(u)
    return lang_users, users
for region, gf in [("SG", {"SG"}), ("MY", {"MY"}), ("SG+MY", {"SG","MY"})]:
    lang_users, users = analyze_non_cny(gf)
    total = len(users)
    zh = len(lang_users.get("zh-CN", set()))
    print(f"  [{region}] 非CNY付费用户={total:,}, zh-CN={zh:,} ({zh/total*100:.1f}% if total else 0%)")

# ---- save Excel ----
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
wb = openpyxl.Workbook()
hdr_fill = PatternFill("solid", fgColor="D9D9D9")

# sheet 1: key answer
ws = wb.active; ws.title = "CNY付费用户_翻译语言"
ws.append(["地区","CNY付费用户总数","其中主导翻译=简中(zh-CN)人数","简中占比%"])
for c in range(1,5): ws.cell(1,c).font=Font(bold=True); ws.cell(1,c).fill=hdr_fill
for region in ("SG","MY","SG+MY"):
    r = result[region]
    t = r["total"]; z = r["zh"]
    ws.append([region, t, z, round(z/t*100,1) if t else 0])

# sheet 2: full lang distribution per region (CNY payers)
ws2 = wb.create_sheet("CNY付费_语言明细")
ws2.append(["地区","主导翻译语言","用户数","占该地区CNY付费用户%"])
for c in range(1,5): ws2.cell(1,c).font=Font(bold=True); ws2.cell(1,c).fill=hdr_fill
for region in ("SG","MY","SG+MY"):
    r = result[region]; t = r["total"]
    for lang, us in sorted(r["lang_users"].items(), key=lambda x:-len(x[1])):
        ws2.append([region, str(lang), len(us), round(len(us)/t*100,1) if t else 0])

# sheet 3: notes
ws3 = wb.create_sheet("结论与口径")
notes = [
 ["SG/MY 地区【CNY 付费用户】的主导翻译语言（VPN 识别代理）"],
 [""],
 ["问题: CNY 付费的 SG/MY 用户里，有多少「平时翻译语言」是简体中文(zh-CN)? "
  "这些很可能是真实的中国用户(用 VPN 后 IP 落在 SG/MY，被主导地理归入 SG/MY，"
  "却在网页/插件用 CNY 付费、且主要翻译目标是简中)。"],
 [""],
 ["方法:"],
 ["1. 地区归属(同 T107b/T107e): 付费订单 userid -> imt_deviceinfo -> imm_regional_activation，"
  "取该用户全历史最常出现的 real_geo(主导国家) = SG / MY。"],
 ["2. 主导翻译语言: 同一份 imm_regional_activation，按用户聚合 target_language 的出现天数，取最多者(平时语言)。"],
 ["3. CNY 付费用户: 该用户在付费窗口内有 >=1 笔 currency=CNY(UPPER) 的 finished 付费订单(含实付/兑换码/onetime)。"],
 ["4. 时间窗: 付费订单 2025-11~2026-11(北京时间)；激活历史 2020~2026 全量(代表平时)。"],
 [""],
 ["口径风险:"],
 ["- 主导地理/主导语言都用「最多出现」稀释 VPN 偶发尖峰，但单用户若长期多地混杂仍可能错归。"],
 ["- 移动端(iOS/安卓)设备号多不在 imt_deviceinfo，取不到国家/语言，本表已排除这些用户(属 NO_GEO)。"],
 ["- zh-CN 精确匹配字符串 'zh-CN'；其它变体(如 zh、zh_TW)单独列出，不计入简中。"],
 ["- 此计数是【用户数】(去重)，不是订单数或金额。"],
]
for line in notes: ws3.append([line[0]])
ws3.cell(1,1).font=Font(bold=True)

path = OUT / "sg_my_cny_payers_translation_lang_202511_202611.xlsx"
wb.save(path)
print("\nSAVED:", path)
