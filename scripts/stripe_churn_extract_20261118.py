"""T127 Stripe 主动取消流失分析 —— 全量取数脚本（只读）。

纪律：唯一网络出口是 GET/list（stripe_client）；Key 从本地 .env 读，绝不打印；
429 退避；不写库、不建同步/定时任务。缓存落 output/stripe_behavior/。

产出 churn_subs.json = 全量 status=canceled 订阅的精简字段（含取消时点/reason/comment/invoice/price）。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stripe_client as sc  # noqa: E402

OUT = ROOT / "output" / "stripe_behavior"
OUT.mkdir(parents=True, exist_ok=True)
BJ = timezone(timedelta(hours=8))


def bjday(ts: int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, BJ).strftime("%Y-%m-%d")


def slim(s: dict) -> dict:
    cd = s.get("cancellation_details") or {}
    items = (s.get("items") or {}).get("data") or []
    first = items[0] if items else {}
    price = first.get("price") or {}
    return {
        "id": s.get("id"),
        "created": s.get("created"),
        "created_bj": bjday(s.get("created")),
        "canceled_at": s.get("canceled_at"),
        "canceled_bj": bjday(s.get("canceled_at")),
        "status": s.get("status"),
        "reason": cd.get("reason"),
        "comment": cd.get("comment"),
        "latest_invoice": s.get("latest_invoice"),
        "customer": s.get("customer"),
        "price_id": price.get("id"),
        "price_unit_amount": price.get("unit_amount"),
        "price_currency": price.get("currency"),
        "price_interval": (price.get("recurring") or {}).get("interval"),
        "product": price.get("product"),
    }


def fetch_all(max_pages: int = 600) -> list[dict]:
    # 取消紧跟创建：用 created 宽窗预过滤（9-01 起），避免把 4 万+ 全历史拉完；
    # 精确窗口在报告脚本按 canceled_at 北京日切，这里只做粗筛。
    created_gte = int(datetime(2026, 9, 1, tzinfo=BJ).timestamp())
    rows: list[dict] = []
    sa = None
    t0 = time.time()
    for pg in range(max_pages):
        p = {"status": "canceled", "created[gte]": created_gte, "limit": 100}
        if sa:
            p["starting_after"] = sa
        st, body = sc.get("/subscriptions", p)
        if st != 200:
            raise RuntimeError(f"GET /subscriptions failed {st}: {(body.get('error') or {}).get('message')}")
        data = body.get("data") or []
        rows.extend(slim(s) for s in data)
        if pg % 10 == 0:
            print(f"  page {pg}: {len(rows)} rows, {time.time()-t0:.0f}s", flush=True)
        if not body.get("has_more") or not data:
            break
        sa = data[-1].get("id")
    else:
        raise RuntimeError(f"超过 max_pages={max_pages}，请检查")
    return rows


if __name__ == "__main__":
    t0 = time.time()
    rows = fetch_all()
    path = OUT / "churn_subs.json"
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print("TOTAL", len(rows), f"{time.time()-t0:.0f}s", "saved", path.name)
    print("reason:", Counter(r["reason"] for r in rows).most_common())
    print("canceled_bj range:", min(r["canceled_bj"] for r in rows if r["canceled_bj"]),
          "->", max(r["canceled_bj"] for r in rows if r["canceled_bj"]))
