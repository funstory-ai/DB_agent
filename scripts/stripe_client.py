"""Stripe 只读客户端（T124/T126）。
纪律：唯一网络出口是 GET/list；Key 从环境变量 STRIPE_API_KEY 读，绝不打印；
429 指数退避；分页游标迭代器。禁止在此模块发 POST/DELETE/UPDATE。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

BASE = "https://api.stripe.com/v1"
S = requests.Session()


def _key() -> str:
    k = os.environ.get("STRIPE_API_KEY", "")
    if not k.startswith(("rk_live_", "sk_live_", "rk_test_")):
        raise RuntimeError("STRIPE_API_KEY 未加载 / 非 Stripe Key；请写入本地 .env")
    return k


def get(path: str, params: dict | None = None, api_version: str | None = None):
    """发一个只读 GET。返回 (status, json)。429/5xx 退避重试。"""
    headers = {"Authorization": f"Bearer {_key()}"}
    if api_version:
        headers["Stripe-Version"] = api_version
    last = None
    for attempt in range(6):
        try:
            r = S.get(BASE + path, params=params or {}, headers=headers, timeout=30)
        except Exception as e:
            last = repr(e)
            time.sleep(1.5 * (2 ** attempt))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(1.5 * (2 ** attempt))
            continue
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}
    return None, {"error": {"message": f"retries exhausted: {last}"}}


def iterate(path: str, params: dict | None = None, api_version: str | None = None,
            page_limit: int = 100, max_pages: int = 1000):
    """list 游标迭代：逐页 yield 对象。按 id 前向游标，避开 offset 漂移。"""
    params = dict(params or {})
    params["limit"] = page_limit
    starting_after = None
    pages = 0
    while pages < max_pages:
        p = dict(params)
        if starting_after:
            p["starting_after"] = starting_after
        st, body = get(path, p, api_version=api_version)
        if st != 200:
            raise RuntimeError(f"GET {path} failed: {st} {(body.get('error') or {}).get('message')}")
        data = body.get("data") or []
        for obj in data:
            yield obj
        pages += 1
        if not body.get("has_more") or not data:
            break
        starting_after = data[-1].get("id")
    else:
        raise RuntimeError(f"GET {path}: 超过 max_pages={max_pages} 页，请缩小时间窗")


if __name__ == "__main__":
    st, acct = get("/balance")
    print("balance GET status:", st, "| keys:", list(acct.keys()) if st == 200 else acct)
