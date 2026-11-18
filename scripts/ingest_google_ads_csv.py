"""T119：Google Ads 后台导出 CSV -> Databend growth.google_ads_daily。

一阶段用法（用户手工导出 CSV 后）：
    F:/python312/python.exe scripts/ingest_google_ads_csv.py --file output/google_ads/xxx.csv
    F:/python312/python.exe scripts/ingest_google_ads_csv.py --file output/google_ads/xxx.csv --write

自检（不依赖任何外部文件、不写库）：
    F:/python312/python.exe scripts/ingest_google_ads_csv.py --selftest

设计口径：
  - 表头自动探测：Google Ads UI 导出常在前面带报表标题/日期范围行，末尾带「总计」行；
  - 金额按账户币种原值（USD）入库，若列里是 micros 需先由 API producer 除以 1e6；
  - 日期为广告账户时区自然日，account_timezone 未确认时留空并在报告里提示；
  - 重放安全：同一 ingest_batch 先 DELETE 再 INSERT，不会重复累计；
  - 默认 dry-run，只有显式 --write 才写库。
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db_writer as w  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

ALIASES = {
    "report_date": ["day", "date", "日期", "天", "日", "segment.date", "日期范围"],
    "campaign_name": ["campaign", "campaign name", "广告系列", "广告系列名称", "广告活动"],
    "campaign_id": ["campaign id", "广告系列 id", "广告系列id"],
    "ad_group_name": ["ad group", "广告组"],
    "ad_group_id": ["ad group id", "广告组 id"],
    "keyword_text": ["keyword", "关键词", "search term", "搜索字词"],
    "clicks": ["clicks", "点击", "点击次数", "点击量"],
    "impressions": ["impressions", "展示", "展示次数", "曝光"],
    "cost_amount": ["cost", "花费", "费用", "cost (usd)", "spend", "成本"],
    "average_cpc": ["avg. cpc", "average cpc", "平均每次点击费用", "平均 cpc", "平均点击成本"],
    "conv_count": ["conversions", "转化", "转化次数"],
    "conv_value": ["conv. value", "conversion value", "转化价值", "转化额"],
}

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y年%m月%d日"]


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "utf-16", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别 CSV 编码：{path}")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def match_columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, h in enumerate(header):
        hn = norm(h)
        for key, aliases in ALIASES.items():
            if key in found:
                continue
            for a in aliases:
                if hn == a or hn.startswith(a) or (a in hn and len(a) >= 3):
                    found[key] = i
                    break
    return found


def detect_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    best = (-1, {}, -1)
    for i, row in enumerate(rows[:12]):
        cols = match_columns(row)
        required = {"report_date", "clicks", "impressions"}
        score = len(cols) + (5 if required.issubset(cols) else 0)
        if score > best[2]:
            best = (i, cols, score)
    if best[0] < 0 or not {"report_date", "clicks"}.issubset(best[1]):
        raise ValueError("找不到表头：需至少包含「日期/Day」与「点击/Clicks」两列。可用 --header-row 指定行号。")
    return best[0], best[1]


def parse_date(s: str):
    v = str(s or "").strip().strip('"')
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    return None


def parse_num(s) -> Decimal:
    v = str(s if s is not None else "").strip()
    if v in ("", "--", "-", "N/A", "—"):
        return Decimal("0")
    neg = v.startswith("(") and v.endswith(")")
    v = re.sub(r"[^\d.\-]", "", v.replace(",", ""))
    if v in ("", "-", ".", "-."):
        return Decimal("0")
    d = Decimal(v)
    return -d if neg else d


def parse_rows(text: str, header_row: int | None = None) -> tuple[list[dict], dict]:
    rows = list(csv.reader(io.StringIO(text)))
    if header_row is None:
        hidx, cols = detect_header(rows)
    else:
        hidx, cols = header_row, match_columns(rows[header_row])
    header = rows[hidx]
    out, skipped = [], 0
    for raw in rows[hidx + 1:]:
        if not raw or all(not str(x).strip() for x in raw):
            continue
        def get(key):
            i = cols.get(key)
            return raw[i] if i is not None and i < len(raw) else ""
        d = parse_date(get("report_date"))
        if d is None:
            skipped += 1  # 合计行 / 说明行
            continue
        rec = {
            "report_date": d,
            "campaign_name": str(get("campaign_name")).strip(),
            "campaign_id": str(get("campaign_id")).strip(),
            "ad_group_name": str(get("ad_group_name")).strip(),
            "ad_group_id": str(get("ad_group_id")).strip(),
            "keyword_text": str(get("keyword_text")).strip(),
            "clicks": int(parse_num(get("clicks"))),
            "impressions": int(parse_num(get("impressions"))),
            "cost_amount": parse_num(get("cost_amount")),
            "average_cpc": parse_num(get("average_cpc")),
            "conv_count": parse_num(get("conv_count")),
            "conv_value": parse_num(get("conv_value")),
        }
        out.append(rec)
    meta = {
        "header_row": hidx,
        "header": header,
        "columns": cols,
        "skipped_rows": skipped,
        "granularity": ("CAMPAIGN" if "campaign_name" in cols else "ACCOUNT"),
    }
    return out, meta


def summarize(records: list[dict]) -> dict:
    if not records:
        return {"rows": 0}
    clicks = sum(r["clicks"] for r in records)
    imp = sum(r["impressions"] for r in records)
    cost = sum((r["cost_amount"] for r in records), Decimal("0"))
    return {
        "rows": len(records),
        "date_min": min(r["report_date"] for r in records),
        "date_max": max(r["report_date"] for r in records),
        "clicks": clicks,
        "impressions": imp,
        "cost": cost,
        "implied_cpc": (cost / clicks) if clicks else Decimal("0"),
        "campaigns": len({r["campaign_name"] for r in records if r["campaign_name"]}),
    }


def daily_table(records: list[dict]) -> str:
    by_day: dict = {}
    for r in records:
        k = r["report_date"]
        a = by_day.setdefault(k, {"clicks": 0, "imp": 0, "cost": Decimal("0")})
        a["clicks"] += r["clicks"]
        a["imp"] += r["impressions"]
        a["cost"] += r["cost_amount"]
    lines = ["  日期        点击     展示        花费    推算CPC"]
    for d in sorted(by_day):
        a = by_day[d]
        cpc = a["cost"] / a["clicks"] if a["clicks"] else Decimal("0")
        lines.append(f"  {d}  {a['clicks']:>7} {a['imp']:>9} {a['cost']:>10.2f} {cpc:>9.4f}")
    return "\n".join(lines)


def check(records: list[dict], args, s: dict) -> list[str]:
    warns = []
    if not records:
        return ["解析到 0 行数据，请检查 CSV 是否为有效报表"]
    if s["clicks"] > s["impressions"]:
        warns.append(f"点击({s['clicks']}) > 展示({s['impressions']})，列名可能错位")
    if any(r["clicks"] < 0 or r["impressions"] < 0 or r["cost_amount"] < 0 for r in records):
        warns.append("存在负数指标，请检查退款/调整行或列映射")
    if args.expect_clicks is not None and s["clicks"] != args.expect_clicks:
        warns.append(f"点击合计 {s['clicks']} ≠ 界面 {args.expect_clicks}，差 {s['clicks'] - args.expect_clicks}")
    if args.expect_cost is not None and abs(s["cost"] - Decimal(str(args.expect_cost))) > Decimal("1"):
        warns.append(f"花费合计 {s['cost']} ≠ 界面 {args.expect_cost}，差 {s['cost'] - Decimal(str(args.expect_cost))}")
    if args.granularity == "ACCOUNT":
        warns.append("当前 CSV 无「广告系列」列 → 只有账户级，撑不起不同渠道转化率")
    if not args.timezone:
        warns.append("未提供账户时区：账户日 ≠ 北京日，与 immdata 对齐前必须确认（--timezone）")
    return warns


def insert_values(rec: dict, args, batch: str, now: str) -> str:
    q = w.sql_quote
    g = args.granularity
    return (
        f"('{rec['report_date']}',{q(g)},{q(args.customer_id)},"
        f"{q(rec['campaign_id'])},{q(rec['campaign_name'])},"
        f"{q(rec['ad_group_id'])},{q(rec['ad_group_name'])},'',"
        f"{q(rec['keyword_text'])},"
        f"{rec['clicks']},{rec['impressions']},{rec['cost_amount']},{rec['average_cpc']},"
        f"{rec['conv_count']},{rec['conv_value']},"
        f"{q(args.currency)},{q(args.timezone)},{q(args.metric_flags)},"
        f"{q(getattr(args, 'source_type', 'CSV'))},{q(args.source_file)},{q(batch)},'{now}')"
    )


def write_db(records: list[dict], args, batch: str, s: dict,
             replace_scope: str | None = None) -> None:
    """写入一批事实。

    replace_scope 给定时（自动同步用）按「账号 + 日期窗」整段替换，
    重跑幂等且不会与历史批次产生重复行；不给定时沿用按 batch 替换。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if replace_scope:
        w.execute("DELETE FROM growth.google_ads_daily WHERE " + replace_scope)
    else:
        w.execute("DELETE FROM growth.google_ads_daily WHERE ingest_batch = " + w.sql_quote(batch))
    w.execute("DELETE FROM growth.ingest_log WHERE ingest_batch = " + w.sql_quote(batch))
    prefix = "INSERT INTO growth.google_ads_daily VALUES "
    for i in range(0, len(records), 100):
        chunk = records[i:i + 100]
        w.execute(prefix + ",".join(insert_values(r, args, batch, now) for r in chunk))
    w.execute(
        "INSERT INTO growth.ingest_log VALUES ("
        + ",".join([
            w.sql_quote(batch), w.sql_quote(getattr(args, "source_type", "CSV")),
            w.sql_quote(args.source_file),
            w.sql_quote(args.granularity), str(s["rows"]),
            f"'{s['date_min']}'", f"'{s['date_max']}'",
            str(s["clicks"]), str(s["impressions"]), str(s["cost"]),
            w.sql_quote(args.note), f"'{now}'",
        ]) + ")"
    )
    _, rows = w.execute("SELECT count(*) FROM growth.google_ads_daily")
    print(f"[WRITE] 批次 {batch} 已入库；growth.google_ads_daily 现有 {rows[0][0]} 行")


SELFTEST_CSV = """广告系列报告,2026/11/09-2026/11/15
日期,广告系列,点击次数,展示次数,花费,平均每次点击费用
2026-11-09,googlekeywords_pdf_translate,742,\"5,120\",\"$223.40\",\"$0.30\"
2026-11-10,googlekeywords_pdf_translate_zh-Hans,810,\"5,600\",\"$245.10\",\"$0.30\"
总计,,\"1,552\",\"10,720\",\"$468.50\",\"$0.30\"
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="Google Ads 导出的 CSV 路径")
    ap.add_argument("--selftest", action="store_true", help="用内置样例验证解析器，不写库")
    ap.add_argument("--write", action="store_true", help="真正写库（默认仅 dry-run）")
    ap.add_argument("--header-row", type=int, help="强制指定表头行号（0 起）")
    ap.add_argument("--customer-id", default="4623896831")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--timezone", default="", help="广告账户时区，如 Asia/Shanghai")
    ap.add_argument("--granularity", default="", help="ACCOUNT/CAMPAIGN/KEYWORD；留空自动判定")
    ap.add_argument("--batch", default="", help="导入批次 ID；留空按文件名+范围生成")
    ap.add_argument("--note", default="")
    ap.add_argument("--expect-clicks", type=int)
    ap.add_argument("--expect-cost", type=float)
    args = ap.parse_args()

    if args.selftest:
        text = SELFTEST_CSV
        args.source_file = "__SELFTEST__"
        print("[SELFTEST] 内置样例（非真实数据）")
    elif args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"文件不存在：{p}")
            return 2
        text = read_text(p)
        args.source_file = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    else:
        ap.print_help()
        return 2

    records, meta = parse_rows(text, args.header_row)
    if not args.granularity:
        args.granularity = meta["granularity"]
    args.metric_flags = ",".join(
        k for k in ("clicks", "impressions", "cost_amount", "average_cpc", "conv_count", "conv_value")
        if k in meta["columns"]
    )
    s = summarize(records)

    print(f"  表头行: 第 {meta['header_row'] + 1} 行；识别列: {sorted(meta['columns'])}")
    print(f"  粒度: {args.granularity}；跳过非数据行: {meta['skipped_rows']}")
    if not s["rows"]:
        print("  解析到 0 行")
        return 2
    print(f"  数据行: {s['rows']}；日期 {s['date_min']} ~ {s['date_max']}；广告系列 {s['campaigns']} 个")
    print(f"  合计: 点击 {s['clicks']} / 展示 {s['impressions']} / 花费 {s['cost']} / 推算CPC {s['implied_cpc']:.4f}")
    print(daily_table(records))

    warns = check(records, args, s)
    if warns:
        print("\n[校验提示]")
        for x in warns:
            print("  !", x)

    if args.selftest:
        assert s["rows"] == 2 and s["clicks"] == 1552 and s["cost"] == Decimal("468.50"), "自检断言失败"
        print("\n[SELFTEST] 解析器断言通过（双表头/千分位/$/总计行）")
        return 0

    if not args.write:
        print("\n[DRY-RUN] 未写库。确认无误后加 --write")
        return 0

    batch = args.batch or f"{Path(args.source_file).stem}_{s['date_min']}_{s['date_max']}"
    write_db(records, args, batch, s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
