# -*- coding: utf-8 -*-
"""T117：移动端（App 内置浏览器）访问域名 TOP N（canonical）。

同一分析只保留这一份脚本：刷新时改 --end / --days / --top，覆盖输出，不新增 dated 副本。
定稿 SQL 在 sql/reports/query_mobile_top_pages_20261113.sql（按 -- @Q_xxx 分段），
本脚本内嵌与 @Q_MAIN 一致的查询，域名归一/子域合并/剔自家/UV 去重在 Python 侧完成。

交付时须带 WF_TASK=T117（wf 状态机要求已过 sampled）：
    WF_TASK=T117 python scripts/export_mobile_top_pages.py --end 2026-11-12 --days 30 --top 100
抽样阶段用 --dry-run（只打印关键数字、不写文件，不设 WF_TASK，绕开交付门禁）：
    python scripts/export_mobile_top_pages.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import get_cursor  # noqa: E402

# ---- wf 硬门禁：交付前必须过抽样（设 WF_TASK 时强制） ----
if os.environ.get("WF_TASK"):
    import wf as _wf

    _wf.require(os.environ["WF_TASK"], "sampled")

SQL_FILE = ROOT / "sql" / "reports" / "query_mobile_top_pages_20261113.sql"
OUT_DEFAULT = ROOT / "output" / "mobile_top_pages_20261113.xlsx"

ZERO_DEV = "00000000-0000-0000-0000-000000000000"
INVALID_DOMAINS = {"", "unknown", "null", "none", "undefined", "-", "about:blank"}
SUB_PREFIX = re.compile(r"^(www|m|cn|en|amp|mobile)\.(.+)$")
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?\.[a-z0-9\-]{2,}$")
OS_KEYS = ("android", "ios", "ipados", "other")
VER_KEYS = ("com", "cn", "other")


def window(end: date, days: int):
    """北京日 [end-days+1, end] -> UTC 常量上下界（北京日 D = UTC (D-1)16:00 ~ D16:00）。"""
    start_day = end - timedelta(days=days - 1)
    utc_start = datetime.combine(start_day - timedelta(days=1), datetime.min.time()) + timedelta(hours=16)
    utc_end = datetime.combine(end, datetime.min.time()) + timedelta(hours=16)
    day_labels = [(start_day + timedelta(days=i)).isoformat() for i in range(days)]
    return utc_start, utc_end, day_labels


def main_sql(utc_start: datetime, utc_end: datetime) -> str:
    return f"""
SELECT get(try_parse_json(ex_char_arg1), 'domain') AS domain,
       device_id,
       os_name,
       ex_char_arg10 AS app_variant,
       created_ts
FROM immdata.user_behaviour
WHERE created_ts >= '{utc_start:%Y-%m-%d %H:%M:%S}'
  AND created_ts <  '{utc_end:%Y-%m-%d %H:%M:%S}'
  AND event_name = 'webview_visit'
  AND lower(os_name) IN ('android', 'ios', 'ipados')
"""


def normalize_domain(raw) -> str | None:
    """原始 domain 值 -> 归一 host：去协议/路径/端口、小写、循环合并常见子域前缀。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    s = s.replace("\\/", "/")
    s = re.sub(r"^\s*https?://", "", s, flags=re.I)
    s = s.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    s = s.strip().lower().rstrip(".")
    if s in INVALID_DOMAINS or " " in s or not s:
        return None
    while True:
        m = SUB_PREFIX.match(s)
        if not m:
            break
        rest = m.group(2)
        if "." not in rest:  # 不要把 x.com 截成 com
            break
        s = rest
    if not HOST_RE.match(s):
        return None
    return s


def is_self_host(host: str) -> bool:
    """剔除自家域名（含全部子域与 .cn / .com）。translify.ai 不属于本规则，保留并注明。"""
    return "immersivetranslate" in host


def bj_day(ts) -> str:
    return (ts + timedelta(hours=8)).date().isoformat()


def fetch_rows(sql: str):
    cur = get_cursor()
    try:
        cur.execute(sql)
        while True:
            batch = cur.fetchmany(10000)
            if not batch:
                break
            for r in batch:
                yield tuple(r.values()) if hasattr(r, "values") else tuple(r)
    finally:
        cur.close()


def collect(end: date, days: int, top: int) -> dict:
    utc_start, utc_end, day_labels = window(end, days)
    host_ids: dict[str, int] = {}
    host_names: list[str] = []
    dev_ids: dict[str, int] = {}

    pv_by_host: Counter = Counter()
    dev_by_host: dict[int, set] = defaultdict(set)
    days_by_host: dict[int, set] = defaultdict(set)
    os_pv: dict[int, Counter] = defaultdict(Counter)
    ver_pv: dict[int, Counter] = defaultdict(Counter)
    day_pv: dict[int, Counter] = defaultdict(Counter)
    pv_by_day: Counter = Counter()
    stats = dict(rows=0, no_domain=0, invalid_domain=0, self_pv=0,
                 no_dev=0, zero_dev=0, total_uv_raw=0, pv_kept=0)

    t0 = time.time()
    for raw_domain, device, os_name, variant, ts in fetch_rows(main_sql(utc_start, utc_end)):
        stats["rows"] += 1
        d = bj_day(ts)
        pv_by_day[d] += 1
        dev = None if device is None else str(device)
        if not dev:
            stats["no_dev"] += 1
        elif dev == ZERO_DEV:
            stats["zero_dev"] += 1
        if raw_domain is None or str(raw_domain).strip() in ("", "null", "NULL"):
            stats["no_domain"] += 1
        host = normalize_domain(raw_domain)
        if host is None:
            stats["invalid_domain"] += 1
            continue
        if is_self_host(host):
            stats["self_pv"] += 1
            continue

        hid = host_ids.get(host)
        if hid is None:
            hid = len(host_names)
            host_ids[host] = hid
            host_names.append(host)
        pv_by_host[hid] += 1
        stats["pv_kept"] += 1
        day_pv[hid][d] += 1
        days_by_host[hid].add(d)
        osk = str(os_name).lower() if os_name else "other"
        os_pv[hid][osk if osk in OS_KEYS else "other"] += 1
        vk = str(variant) if variant in ("com", "cn") else "other"
        ver_pv[hid][vk] += 1

        dk = None
        if dev and dev != ZERO_DEV:
            dk = dev_ids.get(dev)
            if dk is None:
                dk = len(dev_ids) + 1
                dev_ids[dev] = dk
            dev_by_host[hid].add(dk)

    ranked = sorted(pv_by_host.items(), key=lambda kv: (-kv[1], host_names[kv[0]]))[:top]
    stats["elapsed_s"] = round(time.time() - t0, 1)
    stats["distinct_device_all"] = len(dev_ids)
    stats["hosts_kept"] = len(host_names)
    return dict(end=end, days=days, top=top, utc_start=utc_start, utc_end=utc_end,
                day_labels=day_labels, host_names=host_names, ranked=ranked,
                pv_by_host=pv_by_host, dev_by_host=dev_by_host, days_by_host=days_by_host,
                os_pv=os_pv, ver_pv=ver_pv, day_pv=day_pv, pv_by_day=pv_by_day,
                stats=stats)


def _header(ws, cols):
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_excel(res: dict, out: Path):
    s = res["stats"]
    names = res["host_names"]
    ranked = res["ranked"]
    days = res["day_labels"]
    total_pv = s["pv_kept"]
    wb = Workbook()

    ws = wb.active
    ws.title = "0_摘要"
    _header(ws, ["指标", "值", "说明"])
    rows = [
        ("需求编号", "T117", "移动端访问 TOP 网页（域名级）"),
        ("时间窗（北京自然日）", f"{days[0]} ~ {days[-1]}", f"共 {res['days']} 个完整日"),
        ("UTC 窗口", f"{res['utc_start']} ~ {res['utc_end']}", "北京日 D = UTC (D-1)16:00 ~ D16:00"),
        ("事件", "webview_visit", "App 内置浏览器访问；域名取 ex_char_arg1 JSON 的 domain"),
        ("原始访问事件数", s["rows"], "全窗 webview_visit 事件"),
        ("剔自家/无效后 PV", total_pv, "进入排行的访问次数"),
        ("剔除自家域名 PV", s["self_pv"], "host 含 immersivetranslate，全部子域"),
        ("无效/缺失域名 PV", s["invalid_domain"] + s["no_domain"], "unknown / 空 / 非域名格式"),
        ("归一化后 host 数", s["hosts_kept"], "合并常见子域、剔自家后"),
        ("访问过入榜域名的去重设备", s["distinct_device_all"], "仅统计至少访问过 1 个有效非自家域名的设备，排除空 device_id 与全零占位 UUID；全量 webview_visit 去重设备更大（含只访问自家/无效域名的设备），见定稿 SQL @Q_OVERVIEW"),
        ("空 device_id 事件", s["no_dev"], ""),
        ("全零占位 device_id 事件", s["zero_dev"], "不计入 UV"),
        ("排名指标", "PV + 去重设备 UV", f"TOP {res['top']}，按 PV 降序"),
        ("归一规则", "去协议/路径/端口 → 小写 → 循环合并 www.|m.|cn.|en.|amp.|mobile.", "见 5_口径与抽样"),
        ("⚠️ 数据质量提示", "TOP1 archiveofourown.org 有明显时间断点", "10-14~10-29 日 PV 约 1.9~2.5 万，10-30 起降到 0.05~0.26 万；单设备 30 天最高 3,740 次。机制未证实（P043），不可直接读作「最受欢迎网站」；见 4_按天TOP20"),
        ("按 UV 排的 TOP1", "见 1b_按UV排名TOP100", "按去重设备数排序时 youtube.com 第一，与按 PV 排序不同；两榜并列供对照"),
    ]
    for r in rows:
        ws.append(list(r))
    ws.append([])
    ws.append(["TOP10 快览", "PV", "设备UV"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for hid, pv in ranked[:10]:
        ws.append([names[hid], pv, len(res["dev_by_host"][hid])])
    _widths(ws, [30, 26, 62])

    ws = wb.create_sheet("1_总榜_TOP100")
    _header(ws, ["排名", "域名", "访问次数 PV", "去重设备 UV", "PV 占比 %", "人均访问次数",
                 "覆盖天数", "首次出现日", "末次出现日"])
    for i, (hid, pv) in enumerate(ranked, start=1):
        uv = len(res["dev_by_host"][hid])
        dset = sorted(res["days_by_host"][hid])
        ws.append([i, names[hid], pv, uv, round(pv * 100 / total_pv, 3),
                   round(pv / uv, 2) if uv else None, len(dset), dset[0], dset[-1]])
    _widths(ws, [8, 42, 16, 16, 14, 16, 12, 16, 16])

    # 参考榜：同一批域名改按去重设备 UV 降序（TOP1 与 PV 榜不同），非主口径
    ws = wb.create_sheet("1b_按UV排名TOP100")
    _header(ws, ["排名(按UV)", "域名", "去重设备 UV", "访问次数 PV", "PV 榜排名", "人均访问次数"])
    pv_rank = {hid: i for i, (hid, _pv) in enumerate(ranked, start=1)}
    by_uv = sorted(res["pv_by_host"].items(),
                   key=lambda kv: (-len(res["dev_by_host"][kv[0]]), names[kv[0]]))[:res["top"]]
    for i, (hid, pv) in enumerate(by_uv, start=1):
        uv = len(res["dev_by_host"][hid])
        ws.append([i, names[hid], uv, pv, pv_rank.get(hid),
                   round(pv / uv, 2) if uv else None])
    _widths(ws, [14, 42, 16, 16, 14, 16])

    ws = wb.create_sheet("2_分OS")
    _header(ws, ["排名", "域名", "Android PV", "iOS PV", "iPadOS PV", "其它 PV", "合计 PV"])
    for i, (hid, pv) in enumerate(ranked, start=1):
        c = res["os_pv"][hid]
        ws.append([i, names[hid], c["android"], c["ios"], c["ipados"], c["other"], pv])
    _widths(ws, [8, 42, 16, 14, 16, 14, 14])

    ws = wb.create_sheet("3_分版本")
    _header(ws, ["排名", "域名", "com（国际版）PV", "cn（国内版）PV", "其它 PV", "合计 PV"])
    for i, (hid, pv) in enumerate(ranked, start=1):
        c = res["ver_pv"][hid]
        ws.append([i, names[hid], c["com"], c["cn"], c["other"], pv])
    _widths(ws, [8, 42, 20, 20, 14, 14])

    ws = wb.create_sheet("4_按天TOP20")
    _header(ws, ["排名", "域名"] + days + ["合计"])
    for i, (hid, pv) in enumerate(ranked[:20], start=1):
        c = res["day_pv"][hid]
        ws.append([i, names[hid]] + [c[d] for d in days] + [pv])
    _widths(ws, [8, 42] + [12] * len(days) + [14])

    ws = wb.create_sheet("5_口径与抽样")
    _header(ws, ["项", "内容"])
    notes = [
        ("口径", "移动端 = user_behaviour 中 os_name ∈ android/iOS/iPadOS 的 webview_visit（App 内置浏览器访问）。不是系统浏览器全部访问，也不是插件翻译事件。"),
        ("域名来源", "ex_char_arg1 的 JSON domain 键；值格式混杂（https://x.com/、x.com、m.youtube.com），必须归一。库内无具体页面 URL（全窗仅极少量带真实路径），故「TOP 网页」实为「TOP 站点域名」。"),
        ("归一", "去引号/反转义 → 去协议 → 去路径、query、fragment、端口 → 小写 → 循环合并 www./m./cn./en./amp./mobile. 前缀 → 校验 host 格式。例：m.youtube.com、www.youtube.com → youtube.com；cn.bing.com、www.bing.com → bing.com。简单前缀合并，非完整 eTLD+1 解析。"),
        ("剔自家", "host 含 immersivetranslate 的全部子域与 .com/.cn 均剔除（app./dash./onboarding. 等）；translify.ai 未纳入剔除规则，保留。"),
        ("UV", "访问该域名的去重埋点 device_id；排除空值与全零占位 UUID。同一设备访问多个域名在各域名各计 1，不可跨域名相加。P037：移动端 device_id 大多不在 imt_deviceinfo，全程不 JOIN 设备表。"),
        ("PV", "1 条 webview_visit = 1 次访问；按天切片用 created_ts + 8h 的北京自然日。"),
        ("分 OS / 分版本 / 按天", "三张附表只给 PV 拆分，UV 仅总榜给；按天表只列总榜 TOP20 域名。"),
        ("参考榜 1b", "同一批域名按去重设备 UV 降序另出 TOP100，仅作对照，不替代主榜（主榜按 PV 降序）。按 UV 排 TOP1 为 youtube.com，按 PV 排 TOP1 为 archiveofourown.org。"),
        ("无效值剔除", f"全窗 {s['invalid_domain'] + s['no_domain']} PV 未进排行：about:blank / about:srcdoc、127.0.0.1 等本地地址、UUID 形态脏值（domain 字段被写成设备 ID）、unknown 等。"),
        ("功能子域不合并", "只合并 www./m./cn./en./amp./mobile. 前缀；accounts.youtube.com / consent.youtube.com / help.x.com / api.x.com 等功能子域保留为独立 host，未并入主域。"),
        ("⚠️ TOP1 时间断点", "archiveofourown.org 30 天 345,055 PV，但 10-14~10-29 每日约 1.9~2.5 万 PV / 1.4~1.6 千设备，10-30 起骤降至 0.05~0.26 万 PV；30 天单设备最高 3,740 次访问。数据事实已核对（@Q_SAMPLE_AO3），成因（埋点/上报/客户端变更/自动化）未证实，P043 不作因果判断，勿直接读作「最受欢迎网站」。"),
        ("限制", "webview_visit 只覆盖沉浸式翻译 App 内置浏览器；域名上报格式不统一，归一规则变化会改变排名（例：单日不合并子域时 x.com 第一，合并后 youtube.com 第一）；长尾含可疑/成人站点，未做业务分类；抽样 SQL 若用 ex_char_arg1 LIKE 需注意 JSON 斜杠转义（见定稿 SQL @Q_SAMPLE_X 注）。"),
        ("不可用数据源", "user_access_log（唯一带完整 url/site）max(created_ts)=2025-09-05，已停更；translate_page_performance.site_host 有 host 但 device_id 全空，只能 PV。"),
        ("定稿 SQL", "sql/reports/query_mobile_top_pages_20261113.sql（@Q_MAIN 主查询、@Q_OVERVIEW、@Q_SAMPLE_* 抽样）"),
        ("抽样复核", "见任务文档 docs/tasks/query_mobile_top_pages_feasibility_20261113.md「抽样复核」章节；P019 用独立窄 SQL 对拍总量、末日、TOP1/TOP2 域名族。"),
        ("脚本", "scripts/export_mobile_top_pages.py（canonical，--end/--days/--top 可刷新；交付须带 WF_TASK=T117）"),
    ]
    for r in notes:
        ws.append(list(r))
    _widths(ws, [24, 120])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-11-12", help="末个北京自然日 YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--dry-run", action="store_true", help="只打印关键数字，不写文件")
    a = ap.parse_args()

    end = date.fromisoformat(a.end)
    res = collect(end, a.days, a.top)
    s = res["stats"]
    names = res["host_names"]
    print(f"[T117] 北京日 {res['day_labels'][0]} ~ {res['day_labels'][-1]}  "
          f"UTC {res['utc_start']} ~ {res['utc_end']}")
    print(f"rows={s['rows']}  kept_pv={s['pv_kept']}  self_pv={s['self_pv']}  "
          f"invalid_domain_pv={s['invalid_domain']}  no_domain={s['no_domain']}")
    print(f"hosts={s['hosts_kept']}  devices_all={s['distinct_device_all']}  "
          f"no_dev={s['no_dev']}  zero_dev={s['zero_dev']}  elapsed_s={s['elapsed_s']}")
    print(f"day_pv_sum={sum(res['pv_by_day'].values())}  days={len(res['pv_by_day'])}  "
          f"first_day_pv={res['pv_by_day'][res['day_labels'][0]]}  "
          f"last_day_pv={res['pv_by_day'][res['day_labels'][-1]]}")
    print("TOP15 (host, PV, UV):")
    for i, (hid, pv) in enumerate(res["ranked"][:15], start=1):
        print(f"  {i:3d}. {names[hid]:38s} {pv:8d}  {len(res['dev_by_host'][hid]):7d}")
    by_uv = sorted(res["pv_by_host"].items(),
                   key=lambda kv: (-len(res["dev_by_host"][kv[0]]), names[kv[0]]))[:5]
    print("TOP5 by UV (host, PV, UV):")
    for i, (hid, pv) in enumerate(by_uv, start=1):
        print(f"  {i:3d}. {names[hid]:38s} {pv:8d}  {len(res['dev_by_host'][hid]):7d}")
    if a.dry_run:
        print("[dry-run] 未写文件")
        return
    out = Path(a.out)
    write_excel(res, out)
    print(f"[T117] 已写出 {out}")


if __name__ == "__main__":
    main()
