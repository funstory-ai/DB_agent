# -*- coding: utf-8 -*-
"""T058：09 月核心月报 → docx/md，版式对齐 08 月截图样板（P041）。"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

OUT_DOCX = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\2026\沉浸式翻译2026年09月核心数据.docx")
OUT_MD = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\2026\沉浸式翻译2026年09月核心数据.md")

# 仅大标题 + 1/2/3 小标题加粗；正文数字不加粗；段内连续换行、段间空一行
BODY = [
    ("沉浸式翻译2026年09月核心数据", True),
    ("", False),
    ("1、月活基本持平，日活止跌回升", True),
    (
        "沉浸式翻译2026年09月月活用户447.2万，比08月448.7万下降1.5万，单月下降0.3%；相比05月490.0万下降42.8万。",
        False,
    ),
    ("日活用户均值70.3万，相比08月67.9万增长3.5%；", False),
    ("日活峰值为80.0万，相比08月76.8万增长4.2%。", False),
    ("", False),
    ("2、总用量环比趋稳，网页仍略降、视频基本持平", True),
    ("09月翻译总事件32507万个，比08月32684万个下降0.5%；", False),
    ("09月网页翻译14313万个，单月下降1.3%；", False),
    ("09月视频翻译17748万个，单月增长0.1%。", False),
    ("人均网页翻译32.0（08月32.3），人均视频翻译39.7（08月39.5）。", False),
    (
        "整体来看，09月恰逢开学季与暑期流量低谷过后的回补窗口：日活已明显回升，"
        "但翻译总事件环比仅微降0.5%、人均网页仍略低于08月，说明活跃回暖快于用量强度修复。"
        "相对03月高点仍累计低29.5%。结构上网页继续小幅拖累、视频量与人均基本持平，"
        "视频侧仍是更稳的底座；后续若开学流量转化为网页深度使用，总用量才有望跟上日活节奏。",
        False,
    ),
    ("", False),
    ("3、收入明显回升，单月净收入为299.8万", True),
    (
        "相对08月高位回落后的横盘，09月单月净收入为299.8万，环比大增13.7%，"
        "与活跃止跌、开学季付费意愿回升方向一致，现金收入弹性明显强于用量。",
        False,
    ),
    ("同比25年09月289.4万增长3.6%，收入同比仍保持增长，但增幅已明显收窄于此前高基数月份。", False),
    (
        "注：09月自建MRR为335.3万，环比增长1.7%；Stripe MRR为290.6万，环比增长0.9%；"
        "有效订阅用户为42294，环比增长0.5%。订阅盘继续温和下行修复、幅度远小于当月净收入波动，"
        "说明本月收入跳升更多来自当月成交节奏而非订阅存量陡增；趋势判断仍宜以自建MRR为主。",
        False,
    ),
]


def set_run_font(run, size: int = 11, bold: bool = False) -> None:
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "微软雅黑"
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:eastAsia"), "微软雅黑")


def write_docx(path: Path) -> None:
    doc = Document()
    for text, bold in BODY:
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


def write_md(path: Path) -> None:
    lines = []
    for text, bold in BODY:
        if text == "":
            lines.append("")
        elif bold:
            lines.append(f"**{text}**")
        else:
            lines.append(text)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}", flush=True)


def main() -> None:
    write_docx(OUT_DOCX)
    write_md(OUT_MD)


if __name__ == "__main__":
    main()
