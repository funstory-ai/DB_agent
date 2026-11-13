#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105 供应商账单 luna 行探查：计费单元枚举、时间范围、金额格式。"""
import os, unicodedata
import polars as pl

DL = r"C:\Users\86933\Downloads"
BILLS = [
    ("2026-06", "Funstory.ai Limited 推文科技有限公司-6月份账单（20260601-20260701）.xlsx", "订单汇总"),
    ("2026-07", "Funstory.ai Limited 推文科技有限公司-7月份账单（20260701-20260801）.xlsx", "订单汇总"),
    ("2026-08", "Funstory.ai Limited 推文科技有限公司-8月份账单（20260801-20260901）.xlsx", "订单汇总"),
    ("2026-08d", "Funstory.ai Limited 推文科技有限公司-8月份账单（20260801-20260901）.xlsx", "订单明细"),
    ("STAR", "66837208_星图_已完成订单_2026-10-06_2026-11-05_1793938462.xlsx", "已支付订单详单"),
]


def norm(s):
    return "".join("_" if unicodedata.category(ch) == "Pc" else ch for ch in str(s))


for tag, fn, sh in BILLS:
    p = os.path.join(DL, fn)
    d = pl.read_excel(p, engine="calamine", sheet_name=sh)
    print("=" * 110)
    print(f"[{tag}] {sh} shape={d.shape}")
    luna = d.filter(pl.col("模型名称").str.contains("(?i)luna"))
    print(f"luna rows = {luna.height}")
    if luna.height == 0:
        print("  模型名称枚举:", sorted(set(d["模型名称"].drop_nulls().to_list()))[:40])
        continue
    print("  计费单元枚举:")
    for u in sorted(set(norm(x) for x in luna["计费单元"].drop_nulls().to_list())):
        print("   ", u)
    tcols = [c for c in ["创建时间", "开始时间", "结束时间", "账期", "订单创建时间(UTC+8)", "交易生效时间(UTC+8)"] if c in luna.columns]
    for c in tcols:
        vals = [str(x) for x in luna[c].drop_nulls().to_list()]
        print(f"  {c}: min={min(vals) if vals else '-'} max={max(vals) if vals else '-'}")
    show = ["模型名称", "计费单元", "折后价", "列表价", "用量", "计费单位", "订单金额", "原价", "订单总额"] + tcols[:1]
    show = [c for c in show if c in luna.columns]
    print("  样例:")
    for r in luna.select(show).head(8).iter_rows():
        print("   ", " | ".join(str(x)[:70] for x in r))
