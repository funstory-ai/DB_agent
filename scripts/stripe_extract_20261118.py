"""T126 取数：Stripe 侧只读拉取（30天窗口），本地缓存到 output/stripe_behavior/。
只发 GET/list；expand 客户邮箱避免 N+1；每 10 页落一次 checkpoint，可续跑。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stripe_client as sc

OUT = Path(__file__).resolve().parents[1] / "output" / "stripe_behavior"
OUT.mkdir(parents=True, exist_ok=True)
BJ = timezone(timedelta(hours=8))
LO = int(datetime(2026, 10, 19, tzinfo=BJ).timestamp())
HI = int(datetime(2026, 11, 18, tzinfo=BJ).timestamp())


def dump(name, rows):
    with open(OUT / f"{name}.json.tmp", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    os.replace(OUT / f"{name}.json.tmp", OUT / f"{name}.json")


def load(name):
    p = OUT / f"{name}.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else []


def pull(name, path, params, slim, max_pages=800):
    rows = load(name)
    seen = {r["id"] for r in rows}
    # 从最后一条的 created 之后续拉（用 created[lte] 收缩 + 本地去重，规避 starting_after  Across restarts）
    last_created = min((r["created"] for r in rows), default=None)
    p = dict(params)
    if last_created:
        p["created[lte]"] = last_created
    page = 0
    t0 = time.time()
    for obj in sc.iterate(path, p, page_limit=100, max_pages=max_pages):
        if obj.get("id") in seen:
            continue
        seen.add(obj.get("id"))
        rows.append(slim(obj))
        page += 1
        if page % 10 == 0:
            dump(name, rows)
            print(f"  {name}: +{page} pages, total={len(rows)}, {time.time()-t0:.0f}s", flush=True)
    dump(name, rows)
    print(f"{name}: FINAL {len(rows)} rows, {time.time()-t0:.0f}s", flush=True)
    return rows


def slim_invoice(inv):
    c = inv.get("customer")
    email = c.get("email") if isinstance(c, dict) else None
    cid = c.get("id") if isinstance(c, dict) else c
    lines = (inv.get("lines") or {}).get("data") or []
    desc = lines[0].get("description") if lines else None
    price = (lines[0].get("price") or {}).get("id") if lines else None
    return {
        "id": inv.get("id"), "created": inv.get("created"),
        "status": inv.get("status"), "amount_paid": inv.get("amount_paid"),
        "currency": inv.get("currency"), "billing_reason": inv.get("billing_reason"),
        "customer_id": cid, "email": email, "subscription": inv.get("subscription"),
        "payment_intent": inv.get("payment_intent"), "line_desc": desc, "price_id": price,
    }


def slim_tx(o):
    return {"id": o.get("id"), "created": o.get("created"),
            "amount": o.get("amount"), "currency": o.get("currency"),
            "status": o.get("status"), "payment_intent": o.get("payment_intent"),
            "charge": o.get("charge"), "reason": o.get("reason")}


print(f"window UTC [{LO}, {HI})", flush=True)
pull("invoices", "/invoices",
     {"created[gte]": LO, "created[lt]": HI, "expand[]": ["data.customer"]}, slim_invoice)
pull("refunds", "/refunds", {"created[gte]": LO, "created[lt]": HI}, slim_tx)
pull("disputes", "/disputes", {"created[gte]": LO, "created[lt]": HI}, slim_tx)
print("done. Key 未打印。", flush=True)
