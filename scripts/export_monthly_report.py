# -*- coding: utf-8 -*-
"""核心月报 canonical 生成脚本（T103 起）——**系列 SERIES-MR 的 S1 正文流水线**。

⚠️ 自 202611 起，跑完本脚本只完成系列第一环：还须按
`docs/tasks/series_core_monthly_report.md` 执行 S2 矛盾清单 → S3 数据库高维下钻
→ S4 可行动痛点，才算当月任务完成。202610 已验收、按用户要求不补分析。
本脚本**只管正文**；分析 SQL / Excel 另在 `sql/reports/` 与 `output/monthly_report/`。

取代逐月复制的 `export_t031_*` / `export_t058_*`：本脚本是**唯一**入口，
刷新时只改 `--month`（或 `--asof` 由数据自动取最新月），不新增 dated 副本。
见 `docs/norms/query.md`「刷新类分析（canonical 脚本约定）」+ P041 月报正文格式。

数字全部由 `沉浸式翻译<N>月核心业务数据表.xlsx` 计算，正文不写死数字；
只有「段末分析 / 小标题 / 环比同比叙事」按 P041 每月人工重写，放在 NARRATIVE，
用 `{占位符}` 引用计算值，避免文稿与源表脱钩。

日活均值/峰值表内无列，由业务侧提供，集中在 DAU 字典（见 T031 / T058 任务文档）。

用法：
    python scripts/export_monthly_report.py --month 202610
    python scripts/export_monthly_report.py --month 202610 --xlsx <路径> --outdir <目录>
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

import openpyxl
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

# ---- wf 硬门禁：交付前必须过抽样（设 WF_TASK 时强制；未过门直接退出） ----
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E402
if os.environ.get("WF_TASK"):
    import wf as _wf  # noqa: E402
    _wf.require(os.environ["WF_TASK"], "sampled")

DESKTOP = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\2026")

# 业务侧提供，表内无日活列。T031(08月) / T058(09月) 任务文档留档值 + 本次 10 月。
DAU: dict[int, tuple[int, int]] = {
    202607: (740_000, 832_000),
    202608: (679_318, 768_193),
    202609: (702_871, 800_251),
    202610: (683_878, 828_329),  # 用户 2026-11-05 提供
}

# 每月人工重写的定性文案（P041：禁止换数字照抄上月）。{} 为计算值占位符。
NARRATIVE: dict[int, dict[str, str]] = {
    202610: {
        "h1": "1、月活止跌回升，日活均值回落、峰值走高",
        "h2": "2、总用量转增，视频拉动明显、网页仍偏弱",
        "h3": "3、收入自高位回落，单月净收入为{net}万",
        "overall": (
            "整体来看，{cn}月总用量相比03月高点{hi03}万个累计低{gap}%，"
            "较{cn_prev}月的{gap_prev}%收窄{gap_narrow}个百分点，为03月高点以来首次环比转增。"
            "结构上增量集中在视频：视频总量{video_dir}{video_mom}%、人均由{per_video_prev}升至{per_video}，"
            "网页仅{web_dir}{web_mom}%、人均{per_web}与{cn_prev}月基本持平。"
            "日活均值{dau_avg_dir}{dau_avg_mom}%的同时总事件{events_dir}{events_mom}%，"
            "说明本月用量回升来自单人强度、而非活跃人数扩张，且强度提升几乎全在视频侧；"
            "网页深度使用仍未打开，仍是总用量能否持续修复的关键。"
        ),
        "revenue": (
            "相对{cn_prev}月冲高至{net_prev}万，{cn}月单月净收入为{net}万，环比{net_dir}{net_mom}%，"
            "与月活、总用量双双回升形成反向背离；当月净收入的波动幅度仍明显大于订阅存量的变化，"
            "现金收入与用量走势并不总是同步。"
        ),
        "yoy": (
            "同比25年{cn}月{net_yoy_base}万{net_yoy_dir}{net_yoy}%，为2026年以来同比首次转负"
            "（1–9月同比均为正），去年{cn}月是2025年内单月净收入最高的月份，高基数放大了这一降幅。"
        ),
        "note_tail": (
            "自建MRR结束2月以来连续8个月的环比增长、本月转为回落，与Stripe口径的小幅上行方向背离，"
            "趋势判断仍以自建MRR为准；有效订阅继续温和增长，订阅存量并未随当月净收入同步收缩。"
        ),
    },
}


def latest_xlsx() -> Path:
    files = glob.glob(str(DESKTOP / "沉浸式翻译*月核心业务数据表.xlsx"))
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    if not files:
        raise SystemExit("未找到核心业务数据表，请用 --xlsx 指定")
    return Path(max(files, key=os.path.getmtime))


def read_source(xlsx: Path) -> tuple[dict, dict]:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    mon, mrr = {}, {}
    for r in wb["月度数据"].iter_rows(min_row=2, values_only=True):
        if r[0] and str(r[0]).isdigit():
            mon[int(r[0])] = r
    for r in wb["MRR"].iter_rows(min_row=2, values_only=True):
        if r[0] and str(r[0]).isdigit():
            mrr[int(r[0])] = r
    return mon, mrr


def prev_month(m: int) -> int:
    y, mm = divmod(m, 100)
    return (y - 1) * 100 + 12 if mm == 1 else m - 1


def cn(m: int) -> str:
    return f"{m % 100:02d}"


def dirword(v: float) -> str:
    return "增长" if v >= 0 else "下降"


def build_values(m: int, mon: dict, mrr: dict) -> dict:
    p, yoy_m = prev_month(m), m - 100
    for k in (m, p, yoy_m, 202603, 202605):
        if k not in mon or k not in mrr:
            raise SystemExit(f"源表缺月 {k}，无法计算")
    if m not in DAU or p not in DAU:
        raise SystemExit(f"缺 {m} 或 {p} 的业务侧日活值，请先补 DAU 字典")
    c, q, yb = mon[m], mon[p], mrr[yoy_m]
    mc, mq = mrr[m], mrr[p]

    def pc(a, b):
        return (a / b - 1) * 100

    def w(v):
        return v / 1e4

    def s(v, sign=False):
        return f"{v:+.1f}" if sign else f"{abs(v):.1f}"

    dau_avg, dau_peak = DAU[m]
    dau_avg_p, dau_peak_p = DAU[p]
    hi = mon[202603][4]
    gap, gap_p = (hi - c[4]) / hi * 100, (hi - q[4]) / hi * 100
    v = {
        "year": m // 100, "cn": cn(m), "cn_prev": cn(p),
        "mau": s(w(c[1])), "mau_prev": s(w(q[1])),
        "mau_dir": dirword(pc(c[1], q[1])),
        # 差值用「已展示的 1 位小数」相减，保证读者用文中数字相减能对上（与 08/09 月一致）
        "mau_delta": f"{round(w(c[1]), 1) - round(w(q[1]), 1):.1f}",
        "mau_mom": s(pc(c[1], q[1])),
        "mau05": s(w(mon[202605][1])),
        "mau05_gap": f"{round(w(mon[202605][1]), 1) - round(w(c[1]), 1):.1f}",
        "dau_avg": s(w(dau_avg)), "dau_avg_prev": s(w(dau_avg_p)),
        "dau_avg_dir": dirword(pc(dau_avg, dau_avg_p)), "dau_avg_mom": s(pc(dau_avg, dau_avg_p)),
        "dau_peak": s(w(dau_peak)), "dau_peak_prev": s(w(dau_peak_p)),
        "dau_peak_dir": dirword(pc(dau_peak, dau_peak_p)), "dau_peak_mom": s(pc(dau_peak, dau_peak_p)),
        "events": f"{c[4]:.0f}", "events_prev": f"{q[4]:.0f}",
        "events_dir": dirword(pc(c[4], q[4])), "events_mom": s(pc(c[4], q[4])),
        "web": f"{c[5]:.0f}", "web_dir": dirword(pc(c[5], q[5])), "web_mom": s(pc(c[5], q[5])),
        "video": f"{c[8]:.0f}", "video_dir": dirword(pc(c[8], q[8])), "video_mom": s(pc(c[8], q[8])),
        "per_web": s(c[10]), "per_web_prev": s(q[10]),
        "per_video": s(c[12]), "per_video_prev": s(q[12]),
        "hi03": f"{hi:.0f}", "gap": s(gap), "gap_prev": s(gap_p),
        "gap_narrow": f"{round(gap_p, 1) - round(gap, 1):.1f}",
        "net": s(w(mc[4])), "net_prev": s(w(mq[4])),
        "net_dir": dirword(pc(mc[4], mq[4])), "net_mom": s(pc(mc[4], mq[4])),
        "net_yoy_base": s(w(yb[4])),
        "net_yoy_dir": dirword(pc(mc[4], yb[4])), "net_yoy": s(pc(mc[4], yb[4])),
        "mrr_self": s(w(mc[1])), "mrr_self_dir": dirword(pc(mc[1], mq[1])),
        "mrr_self_mom": s(pc(mc[1], mq[1])),
        "mrr_stripe": s(w(mc[2])), "mrr_stripe_dir": dirword(pc(mc[2], mq[2])),
        "mrr_stripe_mom": s(pc(mc[2], mq[2])),
        "subs": f"{mc[3]:.0f}", "subs_dir": dirword(pc(mc[3], mq[3])),
        "subs_mom": s(pc(mc[3], mq[3])),
    }
    return v


def build_body(m: int, v: dict) -> list[tuple[str, bool]]:
    n = NARRATIVE.get(m)
    if not n:
        raise SystemExit(f"NARRATIVE 缺 {m}：P041 要求每月重写段末分析，请先补文案再跑")
    f = lambda key: n[key].format(**v)

    # P041：只加粗大标题 + 1/2/3 小标题；段内指标各占一行不空行；段间空一行。
    return [
        (f"沉浸式翻译{v['year']}年{v['cn']}月核心数据", True),
        ("", False),
        (n["h1"].format(**v), True),
        (
            f"沉浸式翻译{v['year']}年{v['cn']}月月活用户{v['mau']}万，"
            f"比{v['cn_prev']}月{v['mau_prev']}万{v['mau_dir']}{v['mau_delta']}万，"
            f"单月{v['mau_dir']}{v['mau_mom']}%；相比05月{v['mau05']}万下降{v['mau05_gap']}万。",
            False,
        ),
        (f"日活用户均值{v['dau_avg']}万，相比{v['cn_prev']}月{v['dau_avg_prev']}万"
         f"{v['dau_avg_dir']}{v['dau_avg_mom']}%；", False),
        (f"日活峰值为{v['dau_peak']}万，相比{v['cn_prev']}月{v['dau_peak_prev']}万"
         f"{v['dau_peak_dir']}{v['dau_peak_mom']}%。", False),
        ("", False),
        (n["h2"].format(**v), True),
        (f"{v['cn']}月翻译总事件{v['events']}万个，比{v['cn_prev']}月{v['events_prev']}万个"
         f"{v['events_dir']}{v['events_mom']}%；", False),
        (f"{v['cn']}月网页翻译{v['web']}万个，单月{v['web_dir']}{v['web_mom']}%；", False),
        (f"{v['cn']}月视频翻译{v['video']}万个，单月{v['video_dir']}{v['video_mom']}%。", False),
        (f"人均网页翻译{v['per_web']}（{v['cn_prev']}月{v['per_web_prev']}），"
         f"人均视频翻译{v['per_video']}（{v['cn_prev']}月{v['per_video_prev']}）。", False),
        (f("overall"), False),
        ("", False),
        (n["h3"].format(**v), True),
        (f("revenue"), False),
        (f("yoy"), False),
        (
            f"注：{v['cn']}月自建MRR为{v['mrr_self']}万，环比{v['mrr_self_dir']}{v['mrr_self_mom']}%；"
            f"Stripe MRR为{v['mrr_stripe']}万，环比{v['mrr_stripe_dir']}{v['mrr_stripe_mom']}%；"
            f"有效订阅用户为{v['subs']}，环比{v['subs_dir']}{v['subs_mom']}%。" + f("note_tail"),
            False,
        ),
    ]


def set_run_font(run, size: int = 11, bold: bool = False) -> None:
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "微软雅黑"
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:eastAsia"), "微软雅黑")


def write_docx(path: Path, body: list[tuple[str, bool]]) -> None:
    doc = Document()
    for text, bold in body:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing = 1.15
        run = p.add_run(text)
        set_run_font(run, size=14 if bold and text.startswith("沉浸式") else 11, bold=bold)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    print(f"wrote {path}", flush=True)


def write_md(path: Path, body: list[tuple[str, bool]]) -> None:
    lines = [f"**{t}**" if b else t for t, b in body]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=None, help="YYYYMM；缺省取源表最新月")
    ap.add_argument("--xlsx", type=Path, default=None)
    ap.add_argument("--outdir", type=Path, default=DESKTOP)
    a = ap.parse_args()

    xlsx = a.xlsx or latest_xlsx()
    mon, mrr = read_source(xlsx)
    m = a.month or max(k for k in mon if k in mrr)
    v = build_values(m, mon, mrr)
    body = build_body(m, v)
    stem = f"沉浸式翻译{v['year']}年{v['cn']}月核心数据"
    print(f"source={xlsx}  month={m}")
    for t, b in body:
        if t:
            print(("  # " if b else "    ") + t)
    write_docx(a.outdir / f"{stem}.docx", body)
    write_md(a.outdir / f"{stem}.md", body)


if __name__ == "__main__":
    main()
