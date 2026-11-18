"""T123：不同渠道转化率【首版基线】报表（口径由助手自行判断，见 SQL 文件头注释）。

执行的 SQL 全部取自 sql/reports/query_channel_conversion_baseline_20261116.sql 的
Q0/Q1/Q2/Q3/Q4/Q5 分段 —— 定稿 SQL 就是实际跑的 SQL，避免 P043/P044 的口径漂移。

输出：
  output/google_ads/channel_conversion_baseline_YYYYMMDD.xlsx （5 个 sheet）
  output/google_ads/channel_conversion_baseline_YYYYMMDD.csv  （主表）

用法：F:/python312/python.exe scripts/export_channel_conversion_baseline.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402

SQL_FILE = ROOT / "sql" / "reports" / "query_channel_conversion_baseline_20261116.sql"


def load_sql() -> dict[str, str]:
    """按 `-- ==== Qn` 分段；跳过纯注释行。"""
    blocks: dict[str, list[str]] = {}
    cur = None
    for line in SQL_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^--\s*=+\s*Q(\d+)\b", line)
        if m:
            cur = m.group(1)
            blocks[cur] = []
            continue
        if cur and line.strip() and not line.strip().startswith("--"):
            blocks[cur].append(line)
    return {k: "\n".join(v).strip().rstrip(";") for k, v in blocks.items()}


def d(x) -> float:
    return float(x) if x is not None and not isinstance(x, str) else 0.0


def rate(num, den):
    return round(num / den, 6) if den else None


def main() -> int:
    sqls = load_sql()
    need = {"0", "1", "2", "3", "4", "5"}
    assert need.issubset(sqls), f"SQL 分段缺失: {need - set(sqls)}"
    print("[BASELINE] 执行定稿 SQL Q0/Q1/Q2/Q3/Q4/Q5 …")
    _, dup = query(sqls["0"])
    _, ads_rows = query(sqls["1"])
    _, dev_daily = query(sqls["2"])
    _, paid_rows = query(sqls["3"])
    _, inst_rows = query(sqls["4"])
    _, dev_total = query(sqls["5"])
    print(f"  Q1 广告侧 {len(ads_rows)} 行 / Q2 我方逐日 {len(dev_daily)} 行 / "
          f"Q3 分子 {len(paid_rows)} 行 / Q4 安装渠道 {len(inst_rows)} 行 / "
          f"Q5 渠道去重 {len(dev_total)} 行")
    if dup:
        print("  ⚠️ 存在一 campaign 多 UTM，JOIN 会重复计数，需先处理:", dup[:5])

    ads: dict[str, dict] = defaultdict(
        lambda: {"group": "", "name": "", "ccy": "", "clicks": 0,
                 "imp": 0, "cost": Decimal("0")})
    daily: dict[tuple, dict] = defaultdict(
        lambda: {"clicks": 0, "imp": 0, "cost": Decimal("0"), "devices": 0})
    for row in ads_rows:
        dt, grp, uc, cname, ccy, clicks, imp, cost, _cpc = row
        a = ads[uc]
        a.update({"group": grp, "name": cname, "ccy": ccy})
        a["clicks"] += int(clicks or 0)
        a["imp"] += int(imp or 0)
        a["cost"] += cost or Decimal("0")
        k = (str(dt), uc)
        daily[k]["clicks"] += int(clicks or 0)
        daily[k]["imp"] += int(imp or 0)
        daily[k]["cost"] += cost or Decimal("0")
    for dt, uc, devices in dev_daily:
        daily[(str(dt), uc)]["devices"] += int(devices or 0)

    our = {uc: int(n or 0) for uc, n in dev_total}
    paid = {uc: (int(linked or 0), int(pd or 0)) for uc, linked, pd in paid_rows}

    header = ["渠道组", "UTM campaign", "广告系列(后台名)", "币种", "广告点击",
              "展示", "花费CNY", "CPC_CNY", "我方设备(去重)", "点击→到达率",
              "有账号设备", "付费设备(下界)", "设备→付费率", "点击→付费率(下界)",
              "CPA_CNY(下界)", "每设备成本CNY"]
    rows = []
    for uc, a in sorted(ads.items(), key=lambda x: -x[1]["clicks"]):
        devices = our.get(uc, 0)
        linked, pd = paid.get(uc, (0, 0))
        clicks = a["clicks"]
        cost = d(a["cost"])
        rows.append([
            a["group"], uc, a["name"], a["ccy"], clicks, a["imp"], round(cost, 4),
            round(rate(cost, clicks) or 0, 4), devices,
            rate(devices, clicks), linked, pd, rate(pd, devices),
            rate(pd, clicks), round(cost / pd, 2) if pd else None,
            round(cost / devices, 4) if devices else None,
        ])
    # 合计行（分母/分子都按渠道求和，仅作量级核对）
    tot_clicks = sum(r[4] for r in rows)
    tot_imp = sum(r[5] for r in rows)
    tot_cost = sum(r[6] for r in rows)
    tot_dev = sum(r[8] for r in rows)
    tot_linked = sum(r[10] for r in rows)
    tot_paid = sum(r[11] for r in rows)
    rows.append(["合计", "", "", "CNY", tot_clicks, tot_imp, round(tot_cost, 4),
                 round(rate(tot_cost, tot_clicks) or 0, 4), tot_dev,
                 rate(tot_dev, tot_clicks), tot_linked, tot_paid,
                 rate(tot_paid, tot_dev), rate(tot_paid, tot_clicks),
                 round(tot_cost / tot_paid, 2) if tot_paid else None,
                 round(tot_cost / tot_dev, 4) if tot_dev else None])

    print("\n=== 渠道转化基线（11-09~15，默认口径）===")
    print("  ".join(str(x)[:16] for x in header[:8]))
    for r in rows:
        print(f"  {str(r[1])[:38]:<38} 点击{r[4]:>6} 花费¥{r[6]:>10} "
              f"我方设备{r[8]:>5} 付费{r[11]:>3} "
              f"点击→到达 {r[9]} 设备→付费 {r[12]} CPA {r[14]}")

    stamp = datetime.now().strftime("%Y%m%d")
    outdir = ROOT / "output" / "google_ads"
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"channel_conversion_baseline_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(header)
        w.writerows(rows)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter
    wb = Workbook()

    def sheet(title, head, data, widths=None):
        ws = wb.create_sheet(title)
        ws.append(head)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.alignment = Alignment(horizontal="center")
        for r in data:
            ws.append([float(x) if isinstance(x, Decimal) else x for x in r])
        for i, h in enumerate(head, 1):
            ws.column_dimensions[get_column_letter(i)].width = (
                widths[i - 1] if widths else max(12, min(42, len(str(h)) + 6)))
        ws.freeze_panes = "A2"
        return ws

    wb.remove(wb.active)
    sheet("渠道转化基线", header, rows,
          [14, 44, 38, 8, 12, 12, 14, 12, 16, 14, 14, 16, 14, 18, 16, 16])
    daily_rows = []
    for (dt, uc), v in sorted(daily.items()):
        daily_rows.append([dt, uc, v["clicks"], v["imp"], round(d(v["cost"]), 4),
                           v["devices"], rate(v["devices"], v["clicks"])])
    sheet("逐日×渠道", ["北京日", "UTM campaign", "点击", "展示", "花费CNY",
                     "我方设备(当日)", "点击→到达率"], daily_rows)
    inst = [[str(ch), int(n), int(p), rate(int(p), int(n))] for ch, n, p in inst_rows]
    sheet("安装渠道对照", ["installchannel", "新装设备", "付费设备(下界)", "新装→付费率"], inst)

    notes = [
        ["项", "内容"],
        ["最终目标", "结合现有 immdata 数据看不同渠道的转化率（用户 2026-11-16 定主线）"],
        ["本报表状态", "首版基线：口径由助手自行判断并写明，可复算；不是业务定案数字"],
        ["观察窗", "北京日 2026-11-09 ~ 11-15（UTC 11-08 16:00 ~ 11-15 16:00）"],
        ["渠道粒度", "utm_campaign（广告侧经 growth.channel_campaign_map 自动映射）"],
        ["分母A", "广告点击 growth.google_ads_daily（账户本币 CNY，非 MCC 界面 USD 折算）"],
        ["分母B", "我方 imt_campaigninfo 带该 UTM 的去重设备（按渠道整体去重，用 Q5）"],
        ["分子", "分母B 中能桥接 userid 且同窗有 P013 付费单的设备数"],
        ["P013 付费", "finished 且 (amountpaid>0 或 ordertype=code 或 onetime 兑换码)"],
        ["桥接链", "imt_campaigninfo.deviceid → imt_deviceinfo.deviceid → userid → imt_subscriptiongoodsorder"],
        ["★ 关键突破", "广告 URL 自带 utm_campaign，与我方埋点同名；映射由 API 实测解析，非人工猜值"],
        ["⚠️ 限制1", "我方 reference 近 1 日 gclid 命中 0 行；广告侧 click_view 有 GCLID 但无处可连 ⇒ 用户级点击归因做不到"],
        ["⚠️ 限制2", "新装第一跳 UTM 稀疏（T119 Q8：单日 google_sem 新装仅 85 台）；分母B 含存量启动"],
        ["⚠️ 限制3", "付费侧不继承营销渠道（T119 Q5：google 命中 0），分子只能靠设备桥接，是下界"],
        ["⚠️ 限制4", "CPA / 设备→付费率 不可当真实 ROI 引用；严格 7 天归因窗需等 11-22 后数据齐全"],
        ["⚠️ 限制5", "Q2 逐日设备数跨日会重复，禁止相加当渠道总量；汇总一律用 Q5"],
        ["可判定结论", "渠道级（UTM campaign × 日）点击→到达→付费可算；用户级点击→付费归因不可算，需业务侧埋 GCLID"],
        ["数据源", "sql/reports/query_channel_conversion_baseline_20261116.sql（Q0~Q5，本脚本实际执行）"],
        ["生成时间", datetime.now().isoformat(timespec="seconds")],
    ]
    sheet("口径与限制", notes[0], notes[1:], [20, 118])
    ws = wb["口径与限制"]
    for row in ws.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    sheet("映射覆盖校验", ["ads_campaign_name", "n_utm", "map_rows"],
          [list(x) for x in dup] or [["（无一对多 campaign，1:1 映射可直接 JOIN）", "", ""]])

    xlsx = outdir / f"channel_conversion_baseline_{stamp}.xlsx"
    wb.save(xlsx)
    print(f"\n[OUT] {xlsx.relative_to(ROOT)}")
    print(f"[OUT] {csv_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
