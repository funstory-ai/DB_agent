# -*- coding: utf-8 -*-
"""T125: 基于 T027 定稿版，把推文 datapack 推进到 2026Q3。

数据源：output/_t125_q3_source.json（飞书自动同步表 + immdata 只读查询）。
底稿：output/推文datapack-202607_T027.xlsx。
交付：output/推文datapack-2026Q3_T125.xlsx，并复制到桌面（若未被占用）。

原则：历史行（2026Q2 及更早）一个不动，仅追加/插入 Q3。

============================================================================
⚠️⚠️ 禁止重跑警告（2026-11-18 用户明确要求）⚠️⚠️
本脚本是【Q2→Q3 一次性迁移脚本】，内部含 insert_rows 插行 + clone_row_style
手工造样式，且 main() 每次都 copy2(BASE=T027老底稿, OUT) 重建整份文件、
最后 copy2(OUT, DESK) 覆盖桌面。用户会在成品上手工调格式（列宽/行高/合并/
冻结窗格/边框），一旦重跑，手调格式会被脚本的粗糙样式全部冲掉；且在已成型
的 Q3 成品上重跑 insert_rows 还会重复插行。

★ 以后季度更新（如 Q4）绝不要直接重跑本脚本，也不要拿 T027 当底稿。
★ 唯一正确的更新基准 = output/推文datapack-2026Q3_格式基准_T125.xlsx
  （2026-11-18 固化：用户手调好格式的 Q3 成品原样副本，含全部正确格式）。
  新方法：从该基准 copy 出新季度文件 → 只改数据单元格的 value（保留 style），
  按 4 块上三角逐块回填新到期列（见 docs/tasks/audit_datapack_2026q3_20261117.md
  第四轮总结），不 insert_rows、不重建样式、不覆盖用户桌面手调文件（如需同步
  桌面先问用户）。详见 MEMORY.md 的 T125 章节。
============================================================================
"""
from __future__ import annotations
import json, shutil, sys
from copy import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query  # noqa: F401  保留以便脚本自证只读环境
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(r"H:\databend_sql")
SRC = ROOT / "output" / "_t125_q3_source.json"
BASE = ROOT / "output" / "推文datapack-202607_T027.xlsx"
OUT = ROOT / "output" / "推文datapack-2026Q3_T125.xlsx"
DESK = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\推文datapack-202607.xlsx")

D = json.loads(SRC.read_text(encoding="utf-8"))


def clone_row_style(ws, src_row, dst_row, max_col):
    """复制 src_row 的样式到 dst_row（dst_row 须已存在/已插入）。"""
    for c in range(1, max_col + 1):
        s, d = ws.cell(src_row, c), ws.cell(dst_row, c)
        d.font = copy(s.font)
        d.fill = copy(s.fill)
        d.border = copy(s.border)
        d.alignment = copy(s.alignment)
        d.number_format = s.number_format
        d.protection = copy(s.protection)


def num(v):
    """把 '123.4' 或 123.4 转 float；None/'' -> None。"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


# ---- 上三角回填辅助（T125 11-18 修正）----
# 留存表是上三角：cohort 行随时间长出新的留存列。推进到 Q3（2026-09）时，
# 必须把所有历史 cohort 行在 7/8/9 月新到期的列一起回填，不能只追加新 cohort 行。
ASOF_YM = 202609  # Q3 截止年月（北京月）
MON_ABBR = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def ym_add(ym, n):
    """年月整数 + n 月，返回 yyyyMM（如 202604+5=202609）。"""
    y, m = divmod(int(ym), 100)
    t = (y * 12 + (m - 1)) + n
    return (t // 12) * 100 + (t % 12) + 1


def label_ym(label):
    """'Jul-26' -> 202607。"""
    m, yy = str(label).split("-")
    return 2000 + int(yy), MON_ABBR[m]


def label_add(label, n):
    """'Apr-26' +5 -> 202609（返回 yyyyMM 可比较）。"""
    y, m = label_ym(label)
    t = (y * 12 + (m - 1)) + n
    return (t // 12) * 100 + (t % 12) + 1


def is_mlab(s):
    """是否月份标签 'Jul-26' / 'Sep-25'。"""
    return isinstance(s, str) and len(s) >= 6 and s[:3] in MON_ABBR and s[3] == "-"


def sheet_monthly(wb):
    """「月度数据」：脚注下移，第10行写 2026Q3。"""
    ws = wb["月度数据"]
    # 脚注从 G10 移到 G11
    note = ws.cell(10, 7).value
    ws.cell(11, 7).value = note
    ws.cell(10, 7).value = None
    clone_row_style(ws, 9, 10, 8)
    # 飞书月活表 Q3 三月
    mrows = D["月活表"]
    q3 = [r for r in mrows if str(r[0]) in ("202607", "202608", "202609")]
    web = sum(num(r[9]) for r in q3)   # J 网页
    pdf = sum(num(r[10]) for r in q3)  # K PDF
    epub = sum(num(r[11]) for r in q3) # L EPUB
    video = sum(num(r[12]) for r in q3)# M 视频
    trans = web + pdf + epub + video   # 翻译事件数 = 四类之和
    # 累计激活=季末时点=202609 的值（飞书 H 列，单位万）
    activ = num([r for r in q3 if str(r[0]) == "202609"][0][7])
    mau = (4710739 + 4487099 + 4472249) / 3  # 外源月活季均（核心表月活自建）
    vals = ["2026Q3", round(activ), round(trans, 1), round(web), round(video),
            round(pdf, 1), round(epub, 1), round(mau)]
    for c, v in enumerate(vals, 1):
        ws.cell(10, c).value = v
    print("月度数据 Q3:", vals)


# MRR C列（有效订阅用户）取数 SQL：用户 2026-11-17 提供并确认口径。
# 关键修正：bounds 补 n=28（原 n≤27 只到 2026-08，出不了 9 月）；createtime 直接比 DATE，
#   不加 8h（实测加 8h 历史误差从 -6~-20 扩大到 -2~-39，证明不该加）。
# 历史验证：202601~202606 SQL 值 46502/47220/49151/49818/51112/52161，
#   vs datapack 46508/47226/49159/49828/51123/52181，误差 0.01%~0.04%（当前重算略小，订单表日更滚动）。
MRR_SUBS_SQL = r"""
WITH bounds AS (
SELECT DATEADD(month, n, CAST('2024-06-01' AS DATE)) AS as_of
FROM (
SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14
UNION ALL SELECT 15 UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24
UNION ALL SELECT 25 UNION ALL SELECT 26 UNION ALL SELECT 27 UNION ALL SELECT 28
) t
),
member_orders AS (
SELECT userid, createtime,
DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted, 0) = 0 AND orderstatus = 'finished'
AND userid IS NOT NULL AND COALESCE(subscriptionday, 0) > 0
AND (COALESCE(amountpaid, 0) > 0
OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
OR LOWER(COALESCE(ordertype, '')) = 'code')
)
SELECT DATEADD(day, -1, b.as_of) AS month_end,
COUNT(DISTINCT m.userid) AS cnt
FROM bounds b INNER JOIN member_orders m
ON m.createtime < b.as_of AND m.cover_end >= b.as_of
GROUP BY b.as_of ORDER BY b.as_of
"""


def fetch_mrr_q3():
    """MRR Q3 三列口径（用户 2026-11-17 最终确认）：
    - B 列 MRR(RMB)   = 核心表「自建MRR(港币)」÷1.164144（用户"用自建不用 Stripe"）
    - C 列 有效订阅用户 = immdata 月末有效订阅 userid 数（用户给的 SQL，实时查，不写死）
    - D 列 销售总收入   = 留空（财务单独给，用户明确不用我做）
    """
    from openpyxl import load_workbook
    FX = 1.16414435389988
    p = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\2026\沉浸式翻译10月核心业务数据表.xlsx")
    ws = load_workbook(p, data_only=True)["MRR"]
    core = {}
    for r in range(5, ws.max_row + 1):
        ym = ws.cell(r, 1).value
        if ym and str(ym).startswith("2026"):
            core[int(ym)] = ws.cell(r, 2).value  # 自建MRR(港币)
    # C 列：实时跑 SQL，按 month_end 归到 yearMonth
    _, rows = query(MRR_SUBS_SQL)
    subs = {}
    for me, cnt in rows:
        subs[me.year * 100 + me.month] = int(cnt)
    print("MRR C列(SQL) Q3:", {ym: subs.get(ym) for ym in (202607, 202608, 202609)})
    out = []
    for ym in (202607, 202608, 202609):
        self_mrr = core.get(ym)
        out.append((ym, round(self_mrr / FX, 2) if self_mrr else None, subs.get(ym), None))
    return out


def sheet_mrr(wb, mrr_q3):
    """「MRR」：第28-30行写 202607/08/09（D 列留空给财务）。"""
    if not mrr_q3:
        print("MRR Q3: 无数据，跳过")
        return
    ws = wb["MRR"]
    for i, (ym, mrr, subs, rev) in enumerate(mrr_q3):
        r = 28 + i
        clone_row_style(ws, 27, r, 4)
        for c, v in enumerate([ym, mrr, subs, rev], 1):
            ws.cell(r, c).value = v
        print("MRR", r, ym, mrr, subs, rev)
    # 口径脚注（用户 2026-11-17 确认；历史行不动）
    ws.cell(31, 1).value = (
        "注：2026Q3起——MRR(RMB)=核心表自建MRR(港币)÷1.164144（自建口径）；"
        "有效订阅用户=immdata 月末仍有效付费订阅去重 userid（订单finished/未删/付费或兑换码，cover_end≥月末）；"
        "销售总收入(RMB)由财务单独提供，暂空。此前月份为原口径，不回改。"
    )
    ws.cell(31, 1).alignment = copy(ws.cell(27, 1).alignment)
    ws.cell(31, 1).font = copy(ws.cell(27, 1).font)


def sheet_monthly_retention(wb):
    """「月留存（GA）」上三角回填：历史 cohort 行的新到期列 + 追加 07/08/09。

    【修正 2026-11-18 第二轮】上一版只往表尾追加了 3 行新 cohort，历史 cohort
    行在 7/8/9 月新到期的留存列(如 202606 的 m1/m2/m3=314108/205480/170637)
    一个都没回填 —— 飞书源本身是持续扩展的上三角，必须整表回填。
    回填原则：源有人数值 且 当前单元格为空 才填(不覆盖历史已定值/公式)。
    """
    ws = wb["月留存（GA）"]
    fly = D["月留存GA"]
    # ym -> (新增人数, [1..6月留存人数])；右块人数在 row[13:19]
    fmap = {}
    for row in fly:
        if row and isinstance(row[0], (int, float)):
            ym = int(row[0])
            fmap[ym] = (num(row[1]), [num(row[c]) for c in range(13, 19)])

    # 1) 回填所有已存在 cohort 行的新到期留存列（左率 C:H + 右人数 N:S）
    for r in range(2, ws.max_row + 1):
        ym = ws.cell(r, 1).value
        if not isinstance(ym, (int, float)) or int(ym) not in fmap:
            continue
        add, cnts = fmap[int(ym)]
        for j in range(6):
            v = cnts[j]
            if v is None:
                continue
            if ws.cell(r, 14 + j).value in (None, ""):
                ws.cell(r, 14 + j).value = v  # 右块人数
            if add and ws.cell(r, 3 + j).value in (None, ""):
                ws.cell(r, 3 + j).value = round(v / add, 4)  # 左块率

    # 2) 表尾追加 202607/08/09 三个新 cohort（升序）
    for i, ym in enumerate((202607, 202608, 202609)):
        r = 35 + i
        add, cnts = fmap[ym]
        clone_row_style(ws, 34, r, 19)
        ws.cell(r, 1).value = ym
        ws.cell(r, 2).value = add
        ws.cell(r, 12).value = ym
        ws.cell(r, 13).value = add
        for j in range(6):
            v = cnts[j]
            if v is None:
                continue
            ws.cell(r, 14 + j).value = v
            if add:
                ws.cell(r, 3 + j).value = round(v / add, 4)
        print("月留存", r, ym, add, cnts)


def sheet_paid_retention(wb):
    """「付费用户留存率」上三角回填 + 推进 Q3。

    结构：率区第2-31行(A:M) + 年费区第1-36行(O:T) + 人数区第34-63行(A:M)。
    【修正 2026-11-18 第二轮】上一版只插了 Jul/Aug/Sep 三行新 cohort，
    历史 cohort 行(如 Jun-26=898/660/525、May-26 的 m2-m4)在 Q3 新到期的列
    一个都没回填。飞书源下半区(idx38-70)含完整上三角人数，按月份标签回填。

    步骤：
      1) 率区历史公式转硬编码(避免插行后引用错位)；
      2) 第2行插3行 → 写率区/年费区的 Q3 三行；人数区插3行 → 写人数；
      3) 按月份标签，把飞书源人数回填到【所有】cohort 行的空白留存列(率区+人数区)；
      4) Q3 率 = 人数/新增(硬编码)。
    """
    ws = wb["付费用户留存率"]
    fly = D["付费留存"]
    # 飞书下半区(idx>=36)人数行: 月份标签 -> (新增, [1..11月留存人数])
    cnt_map, new_map = {}, {}
    yr_map = {}  # 年费区: 月份标签 -> paid_yearly_user (上半区 O/P)
    for idx, row in enumerate(fly):
        if not row:
            continue
        m = str(row[0])
        c3 = row[2] if len(row) > 2 else None
        if is_mlab(m) and isinstance(c3, (int, float)):  # 人数区(下半, C列人数)
            cnt_map[m] = [num(x) for x in row[2:13]]
        if is_mlab(m) and row[1] is not None:  # 新增人数：与留存是否到期无关
            new_map.setdefault(m, num(row[1]))
        if idx < 37 and len(row) > 15 and is_mlab(str(row[14])) and row[15] is not None:
            yr_map.setdefault(str(row[14]), num(row[15]))
    months = ["Jul-26", "Aug-26", "Sep-26"]

    # 1) 率区历史公式转硬编码：率 = 人数区同行同列 / B
    for r in range(2, 32):
        for c in range(3, 14):  # C:M
            f = ws.cell(r, c).value
            if isinstance(f, str) and f.startswith("="):
                cnt = ws.cell(r + 32, c).value
                new = ws.cell(r, 2).value
                ws.cell(r, c).value = round(cnt / new, 4) if (isinstance(cnt, (int, float)) and new) else None
    # 年费区 R/T 公式(=Q/P, =S/P)转硬编码
    for r in range(1, 37):
        for rate_c, num_c, den_c in [(18, 17, 16), (20, 19, 16)]:
            f = ws.cell(r, rate_c).value
            if isinstance(f, str) and f.startswith("="):
                nu, de = ws.cell(r, num_c).value, ws.cell(r, den_c).value
                ws.cell(r, rate_c).value = round(nu / de, 4) if (isinstance(nu, (int, float)) and de) else None

    # 2) 第2行插3行：率区 + 年费区同步下移；第37行插3行：人数区
    ws.insert_rows(2, 3)
    for i, m in enumerate(months):
        r = 4 - i  # 2,3,4 → Sep,Aug,Jul 最新在上
        clone_row_style(ws, 5, r, 20)
        ws.cell(r, 1).value = m
        ws.cell(r, 2).value = new_map.get(m)
        ws.cell(r, 15).value = m
        ws.cell(r, 16).value = yr_map.get(m)
        ws.cell(r, 17).value = None
        ws.cell(r, 18).value = None
    ws.insert_rows(37, 3)
    for i, m in enumerate(months):
        r = 39 - i  # 37,38,39 → Sep,Aug,Jul
        clone_row_style(ws, 40, r, 13)
        ws.cell(r, 1).value = m
        ws.cell(r, 2).value = new_map.get(m)

    # 3) 上三角回填：按月份标签把飞书人数的空白列补到所有 cohort 行。
    #    率区 r2-34 (3+31)，人数区 r37-69 (3+33)。只填空单元格，不覆盖历史定值。
    def patch_region(row_start, row_end, is_rate):
        for r in range(row_start, row_end + 1):
            lab = ws.cell(r, 1).value
            if not isinstance(lab, str) or lab not in cnt_map:
                continue
            cnts, new = cnt_map[lab], new_map.get(lab)
            for j, v in enumerate(cnts):
                cell = ws.cell(r, 3 + j)  # C:M
                if v is None or cell.value not in (None, ""):
                    continue
                cell.value = round(v / new, 4) if (is_rate and new) else (None if is_rate else v)
    patch_region(2, 34, is_rate=True)    # 率区
    patch_region(37, 69, is_rate=False)  # 人数区

    # 3.5) 【修正 2026-11-18 第三轮】右侧年费区(O:T)上三角回填。
    #      年费区结构：O=base_month, P=paid_yearly_user, Q/R=1年留存(人数/率), S/T=2年留存(人数/率)。
    #      底稿只更新到 Jun-25(1年)/Jun-24(2年)。推进到 Q3(截止2026-09)新增到期 cohort:
    #        1年留存(cohort+12月<=202609): Sep-25/Aug-25/Jul-25 -> Q/R 空
    #        2年留存(cohort+24月<=202609): Sep-24/Aug-24/Jul-24 -> S/T 空
    #      飞书源年费区(O列起, idx<37)含完整人数；R/T 在源里是公式字符串, 用 人数/P 现算。
    #      只填空单元格, 不覆盖历史定值(如 Jun-25 敏感值 1443/0.4494)。
    yr1_map, yr2_map = {}, {}  # 月份标签 -> (1年人数, 2年人数)
    for row in fly:
        if not row or len(row) < 19:
            continue
        lab = row[14]  # O列 base_month
        if is_mlab(lab):
            yr1_map[lab] = num(row[16])  # Q = one_year_retention 人数
            yr2_map[lab] = num(row[18])  # S = two_year_retention 人数
    yr_filled = []
    for r in range(2, ws.max_row + 1):
        lab = ws.cell(r, 15).value  # O列 base_month
        if not is_mlab(lab):
            continue
        base = ws.cell(r, 16).value  # P列 paid_yearly_user
        # 1年留存 Q/R
        if ws.cell(r, 17).value in (None, "") and yr1_map.get(lab) is not None:
            q = yr1_map[lab]
            ws.cell(r, 17).value = q
            ws.cell(r, 18).value = round(q / base, 4) if base else None
            yr_filled.append((lab, "1y", q, round(q / base, 4) if base else None))
        # 2年留存 S/T
        if ws.cell(r, 19).value in (None, "") and yr2_map.get(lab) is not None:
            s = yr2_map[lab]
            ws.cell(r, 19).value = s
            ws.cell(r, 20).value = round(s / base, 4) if base else None
            yr_filled.append((lab, "2y", s, round(s / base, 4) if base else None))
    print("年费区上三角回填:", yr_filled)

    # 4) Q3 三行率区(先清空再按人数算；人数已在步骤2的人数区，率区对照写入)
    for m in months:
        rr = {"Jul-26": 4, "Aug-26": 3, "Sep-26": 2}[m]
        cnts, new = cnt_map.get(m, []), new_map.get(m)
        for j, v in enumerate(cnts):
            if v is not None and new:
                ws.cell(rr, 3 + j).value = round(v / new, 4)
    print("付费留存 Q3 new", [new_map.get(m) for m in months],
          "cnt", [cnt_map.get(m) for m in months], "yr", [yr_map.get(m) for m in months])


def sheet_arpu(wb):
    """「ARPU值」：第1行前插18行作为 2026Q3 块。

    【修正 2026-11-18 第二轮】用户明确要求 ARPU 直接照飞书表原值，不再用
    T027 算法反推。飞书 Q3 块(idx113-128)为公式，data_only 缓存已丢，故用
    用户 11-18 从飞书表读取并核对后的数值硬编码（ARPU 412.26/614.31/771.03）。
    """
    ws = wb["ARPU值"]
    # 用户 2026-11-18 核对的飞书 5sbtqZ 表 2026Q3 块原值
    cm, cy, cx = 7407, 4820, 300
    wm, wy, wx = 0.59, 0.38, 0.02
    price_m, m1, m2, m3 = 69, 3.7, 5.26, 6.04
    price_y, y1, y2, y3 = 579.6, 1, 1.53, 2.01
    price_x, x1, x2, x3 = 1599, 1, 1.53, 2.01
    a1, a2, a3 = 412.26, 614.31, 771.03

    # 插 18 行（照搬 2026Q2 块结构）
    ws.insert_rows(1, 18)
    clone_row_style(ws, 19, 1, 6)
    for src, dst in zip(range(1, 18), range(19, 37)):
        clone_row_style(ws, dst, src, 6)
    def put(r, c, v):
        ws.cell(r, c).value = v
    put(1, 1, "2026Q3")
    put(2, 1, "26年07-09月 新增月费用户"); put(2, 2, "26年07-09月 新增年费用户"); put(2, 3, "26年07-09月 新增max用户")
    put(2, 4, "月费用户占比"); put(2, 5, "年费用户占比"); put(2, 6, "max用户占比")
    for c, v in enumerate([cm, cy, cx, wm, wy, wx], 1): put(3, c, v)
    put(5, 1, "月费实收金额"); put(5, 2, "月费用户1年总续费月数"); put(5, 3, "月费用户2年总续费月数"); put(5, 4, "月费用户3年总续费月数")
    for c, v in enumerate([price_m, m1, m2, m3], 1): put(6, c, v)
    put(8, 1, "年费实收金额"); put(8, 2, "年费用户1年总续费年数"); put(8, 3, "年费用户2年总续费年数"); put(8, 4, "年费用户3年总续费年数")
    for c, v in enumerate([price_y, y1, y2, y3], 1): put(9, c, v)
    put(11, 1, "max实收金额"); put(11, 2, "max用户1年总续费年数"); put(11, 3, "max用户2年总续费年数"); put(11, 4, "max用户3年总续费年数")
    for c, v in enumerate([price_x, x1, x2, x3], 1): put(12, c, v)
    put(13, 1, "2年及以上数据来自于付费留存率的预估推测")
    put(15, 1, "1年ARPU值"); put(15, 2, "2年ARPU值（预估）"); put(15, 3, "3年ARPU值（预估）")
    for c, v in enumerate([a1, a2, a3], 1): put(16, c, v)
    print("ARPU Q3:", [cm, cy, cx], [wm, wy, wx], [m1, m2, m3], [y1, y2, y3], [a1, a2, a3])


def sheet_cohort(wb):
    """「同期群」：第28-30行写 2026-07/08/09（datapack 26列有效）。

    列映射（datapack列 <- 飞书列，1-based）：
      1-12 <- 1-12；13(14-30)<-15；14(>30)<-16；15-19<-17-21；20(60回报)<-22；21-26<-23-28
    飞书 13/14 列(14天转化用户/率) datapack 无，跳过。
    回报率=金额/B(营销)；成本=B/C；转化率=H/C。
    """
    ws = wb["同期群"]
    fly = D["同期群"]
    q3 = [r for r in fly if r and num(r[0]) in (46213, 46244, 46275)]
    # datapack 惯例：每月1日；飞书同期群锚点是当月10日，这里改用当月1日 serial
    q3_serial = [46204, 46235, 46266]  # 2026-07-01 / 08-01 / 09-01
    # datapack列 -> 飞书列索引(1-based)，None=公式列自算
    MAP = {2:2, 3:3, 5:5, 6:6, 8:8,
           10:10, 11:11, 13:15, 14:16, 15:17, 16:18, 18:20, 19:21,
           21:23, 22:24, 24:26, 25:27}
    # 回报率列: datapack列 -> 飞书金额列（回报率=金额/营销B）
    RATE = {4:(2,3), 7:(5,2), 9:(8,3), 12:(10,2), 17:(17,2),
            20:(20,2), 23:(23,2), 26:(26,2)}
    # 转化率(I列=8)用6位精度，其余回报率4位
    RATE_PREC = {9: 6}
    INT_COLS = {2, 3, 6, 8, 11, 16, 19, 22, 25}
    for i, row in enumerate(q3):
        r = 28 + i
        clone_row_style(ws, 27, r, 26)
        ws.cell(r, 1).value = q3_serial[i]
        ws.cell(r, 1).number_format = "yyyy/m/d"
        for dc, fc in MAP.items():
            v = num(row[fc - 1])
            if dc in INT_COLS and v is not None:
                v = round(v)
            ws.cell(r, dc).value = v
        for dc, (amt_fc, den_fc) in RATE.items():
            amt, den = num(row[amt_fc - 1]), num(row[den_fc - 1])
            prec = RATE_PREC.get(dc, 4)
            ws.cell(r, dc).value = round(amt / den, prec) if (amt is not None and den) else None
        print("同期群", r, "serial", q3_serial[i], "营销", ws.cell(r,2).value,
              "激活", ws.cell(r,3).value, "收入", ws.cell(r,5).value)

    # 3.5) 【修正 2026-11-18 第四轮】历史 cohort 行上三角回填。
    #      同期群也是上三角：老 cohort 随时间长出更长窗口列(30/60/90/180天金额/单/率)。
    #      底稿历史行停在旧快照，r22(2026-01)~r27(2026-06) 的新到期窗口列为空。
    #   ★陷阱：飞书源从 2025-12 cohort 起缺「14-30/>30」两列(idx14/15)，
    #     后续窗口字段整体左移 2 位。判据 row[16] 是公式字符串('Q/B')即左移。
    #     正常: 30天=(idx16,17) 60=(19,20) 90=(22,23) 180=(25,26)
    #     左移: 30天=(idx14,15) 60=(17,18) 90=(20,21) 180=(23,24)
    #     已用 r21(2025-12) 完整行逐列验证映射正确。
    #      只填空单元格，不覆盖历史已有值(累计刷新是另一口径，用户未要求)。
    from openpyxl.utils.datetime import from_excel
    fmap = {}
    for row in fly:
        if not row or not isinstance(row[0], (int, float)):
            continue
        dt = from_excel(row[0])
        fmap[(dt.year, dt.month)] = row
    DPW = {"30": (15, 16, 17), "60": (18, 19, 20),
           "90": (21, 22, 23), "180": (24, 25, 26)}  # datapack 金额/单/率列
    FWN = {"30": (16, 17), "60": (19, 20), "90": (22, 23), "180": (25, 26)}
    FWS = {"30": (14, 15), "60": (17, 18), "90": (20, 21), "180": (23, 24)}
    filled = []
    for r in range(2, 28):  # 历史行 r2-r27；Q3 三行 r28-30 已单独写
        a = ws.cell(r, 1).value
        if not hasattr(a, "year"):
            continue
        frow = fmap.get((a.year, a.month))
        if not frow:
            continue
        shifted = isinstance(frow[16], str) and "/" in str(frow[16])
        fwin = FWS if shifted else FWN
        base = num(frow[1])  # 营销费用(率的分母)
        for w, (c_amt, c_ord, c_rate) in DPW.items():
            ai, oi = fwin[w]
            amt = num(frow[ai]) if ai < len(frow) else None
            ordv = num(frow[oi]) if oi < len(frow) else None
            if ws.cell(r, c_amt).value in (None, "") and amt is not None:
                ws.cell(r, c_amt).value = round(amt, 2)
                filled.append((r, w, "金额", round(amt, 2)))
            if ws.cell(r, c_ord).value in (None, "") and ordv is not None:
                ws.cell(r, c_ord).value = round(ordv)
                filled.append((r, w, "单数", round(ordv)))
            if ws.cell(r, c_rate).value in (None, "") and amt is not None and base:
                ws.cell(r, c_rate).value = round(amt / base, 4)
                filled.append((r, w, "回报率", round(amt / base, 4)))
    print("同期群历史行上三角回填", len(filled), "格:", filled)


def sheet_region(wb):
    """「分语言地区付费转化率」：表头改 2026.09，9地区重算。"""
    ws = wb["分语言地区付费转化率"]
    # 表头 B1
    ws.cell(1, 2).value = "2026.09月活"
    mau = D["分语言_月活_202609"]
    paid = D["分语言_付费_202609"]
    name_map = {"zh-CN": "简中", "zh-TW": "繁中", "en": "英语", "ko": "韩语",
                "ja": "日本", "ar": "阿拉伯", "fr": "法语", "de": "德语", "es": "西语"}
    for r in range(2, 11):
        cn = ws.cell(r, 1).value
        code = next((k for k, v in name_map.items() if v == cn), None)
        if not code:
            print("地区未映射", cn); continue
        m, p = mau.get(code), paid.get(code)
        ws.cell(r, 2).value = m
        ws.cell(r, 3).value = p
        ws.cell(r, 4).value = round(p / m, 9) if (m and p) else None
        print("分语言", cn, m, p, round(p / m, 6) if (m and p) else None)


def main():
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    shutil.copy2(BASE, OUT)
    wb = load_workbook(OUT)
    # MRR Q3：自建口径（核心表10月文件）
    mrr_q3 = fetch_mrr_q3()
    sheet_monthly(wb)
    sheet_mrr(wb, mrr_q3)
    sheet_monthly_retention(wb)
    sheet_paid_retention(wb)
    sheet_arpu(wb)
    sheet_cohort(wb)
    sheet_region(wb)
    wb.save(OUT)
    print("wrote", OUT)
    try:
        shutil.copy2(OUT, DESK)
        print("desktop updated")
    except Exception as e:
        print("desktop copy failed (file locked?):", e)


if __name__ == "__main__":
    main()
