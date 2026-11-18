"""Stripe 只读探查（T124，2026-11-18）。
纪律：只用 GET/list；Key 从环境变量 STRIPE_API_KEY 读取，绝不打印；
429 指数退避；账号 id 仅用于确认身份，email/customer 脱敏。
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import query

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
KEY = os.environ.get("STRIPE_API_KEY", "")
if not KEY.startswith("rk_live_"):
    raise SystemExit("STRIPE_API_KEY 未加载或非 rk_live_ 只读 Key，停止")

BASE = "https://api.stripe.com/v1"
BJ = timezone(timedelta(hours=8))
S = requests.Session()
S.headers.update({"Authorization": f"Bearer {KEY}"})


def bj(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(BJ).strftime("%Y-%m-%d %H:%M:%S")


def get(path, params=None):
    """唯一的网络出口：只发 GET。返回 (status, json, stripe_version)。"""
    for attempt in range(6):
        try:
            r = S.get(BASE + path, params=params or {}, timeout=25)
        except Exception as e:
            if attempt == 5:
                return None, {"exception": repr(e)}, None
            time.sleep(1.5 * (2 ** attempt))
            continue
        ver = r.headers.get("Stripe-Version")
        if r.status_code == 429:
            time.sleep(1.5 * (2 ** attempt))
            continue
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:200]}
        return r.status_code, body, ver
    return None, {"exhausted": True}, None


def mask_email(e):
    if not e or "@" not in e:
        return None
    name, dom = e.split("@", 1)
    return name[:2] + "***@" + dom


def section(title):
    print("\n===== " + title + " =====")


# ---- 1. 账号身份 ----
section("1 账号身份 / livemode")
st, acct, ver = get("/account")
print("GET /account status:", st, "Stripe-Version:", ver)
if st == 200:
    print("  id:", acct.get("id"))
    print("  livemode:", acct.get("livemode"), "| country:", acct.get("country"),
          "| default_currency:", acct.get("default_currency"))
    print("  business_type:", acct.get("business_type"), "| charges_enabled:", acct.get("charges_enabled"))
else:
    print("  ", acct)

# ---- 2. 权限矩阵（list limit=1）----
section("2 权限矩阵（各资源 list limit=1；401/403=无权限）")
resources = [
    "customers", "invoices", "subscriptions", "checkout/sessions", "charges",
    "payment_intents", "refunds", "disputes", "prices", "products",
    "balance_transactions", "payouts", "coupons", "events",
]
for res in resources:
    st, body, _ = get("/" + res, {"limit": 1})
    if st == 200:
        print(f"  READ OK   {res:22s} has_more={body.get('has_more')}")
    else:
        err = (body.get("error") or {}).get("code") or (body.get("error") or {}).get("message", "?")
        print(f"  DENIED    {res:22s} status={st} err={err}")

# ---- 3. 真实 ID 反查（验证两边能否对上）----
section("3 真实 ID 反查（取自我方 immdata 的 Stripe 原生 ID）")
INV = "in_1UcomdGc8iUjvqOFGscXHk12"
SUB = "sub_1U5SvgGc8iUjvqOFjqaKgbfP"
CS = "cs_live_bgYhsdTjQkEI5Ke6p6T5dJtAjNdy2RQNBdhDkPyLvVJcDTgCQqGGnDEU2M"
PRICE = "price_1NVaObGc8iUjvqOFc2mK6aMc"

st, inv, _ = get("/invoices/" + INV)
print(f"invoice {INV}: status={st}")
if st == 200:
    print("  amount_paid:", inv.get("amount_paid"), inv.get("currency"),
          "| status:", inv.get("status"), "| created(BJ):", bj(inv.get("created")))
    print("  customer:", inv.get("customer"), "| subscription:", inv.get("subscription"))
    print("  payment_intent:", inv.get("payment_intent"), "| billing_reason:", inv.get("billing_reason"))
    lines = ((inv.get("lines") or {}).get("data") or [])
    if lines:
        print("  line[0] price:", (lines[0].get("price") or {}).get("id"),
              "| desc:", lines[0].get("description"))
    print("  metadata keys:", list((inv.get("metadata") or {}).keys()))
else:
    print("  ", inv)

st, sub, _ = get("/subscriptions/" + SUB)
print(f"subscription {SUB}: status={st}")
if st == 200:
    print("  status:", sub.get("status"), "| current_period_end(BJ):", bj(sub.get("current_period_end")),
          "| cancel_at_period_end:", sub.get("cancel_at_period_end"))
    print("  customer:", sub.get("customer"))
else:
    print("  ", sub)

st, cs, _ = get("/checkout/sessions/" + CS)
print(f"checkout_session {CS[:24]}...: status={st}")
if st == 200:
    print("  amount_total:", cs.get("amount_total"), cs.get("currency"), "| status:", cs.get("status"))
    print("  payment_intent:", cs.get("payment_intent"), "| subscription:", cs.get("subscription"))
    print("  customer:", cs.get("customer"), "| client_reference_id:", cs.get("client_reference_id"))
    print("  metadata keys:", list((cs.get("metadata") or {}).keys()))
    print("  has UTM-like field:", any("utm" in k.lower() for k in cs.keys()),
          "| top-level keys:", sorted(cs.keys()))
else:
    print("  ", cs)

st, pr, _ = get("/prices/" + PRICE)
print(f"price {PRICE}: status={st}")
if st == 200:
    print("  unit_amount:", pr.get("unit_amount"), pr.get("currency"),
          "| recurring:", (pr.get("recurring") or {}).get("interval"), "| product:", pr.get("product"))
else:
    print("  ", pr)

# ---- 4. invoice.customer -> email 能否与我方 join（脱敏）----
section("4 Customer email join 可行性（脱敏）")
if st is not None and isinstance(inv, dict) and inv.get("customer"):
    st, cust, _ = get("/customers/" + str(inv.get("customer")))
    if st == 200:
        print("  customer email(masked):", mask_email(cust.get("email")),
              "| name present:", bool(cust.get("name")))
        print("  address.country:", ((cust.get("address") or {}).get("country")))
    else:
        print("  customer GET status:", st, cust)

# ---- 5. charge 是否带 geo / payment_intent 链 ----
section("5 Charge 侧的 geo 与支付链（猜测验证）")
st, pi, _ = get("/payment_intents/" + str(inv.get("payment_intent"))) if isinstance(inv, dict) and inv.get("payment_intent") else (None, {}, None)
if st == 200:
    charges = ((pi.get("charges") or {}).get("data") or [])
    print("  payment_intent status:", pi.get("status"), "| charges:", len(charges))
    if charges:
        ch = charges[0]
        bd = ch.get("billing_details") or {}
        print("  charge billing country:", (bd.get("address") or {}).get("country"))
        print("  charge payment_method_details type:", list((ch.get("payment_method_details") or {}).keys()))
        print("  charge refunded:", ch.get("refunded"), "| disputed:", bool(ch.get("disputed")))
else:
    print("  payment_intent GET status:", st, "(invoice 无 PI 或无权限)")

# ---- 6. 退款/争议/近窗量级 ----
section("6 退款 / 争议 / 近 30 天 invoice 量级")
since = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())
for res in ("refunds", "disputes", "invoices"):
    st, body, _ = get("/" + res, {"created[gte]": since, "limit": 3})
    if st == 200:
        data = body.get("data") or []
        sample = data[0] if data else {}
        print(f"  {res:10s}: 近30天首页 {len(data)} 条, has_more={body.get('has_more')}",
              "| sample status:", sample.get("status"))
    else:
        print(f"  {res:10s}: status={st}", (body.get("error") or {}).get("code"))

# ---- 7. Checkout Session 与 Accounts 权限缺失的确切权限名 ----
section("7 权限缺口（错误信息里给出的官方权限名）")
for path in ("/checkout/sessions/" + CS, "/account", "/accounts"):
    st, body, _ = get(path, {"limit": 1})
    err = (body.get("error") or {})
    msg = err.get("message", "")
    perm = ""
    if "Enabling " in msg:
        perm = msg.split("Enabling ", 1)[1].split(" permissions", 1)[0]
    print(f"  {path[:38]:38s} status={st} need_permission={perm or '-'}")

# ---- 8. 时区对齐：invoice.created(BJ) vs 我方 createtime ----
section("8 时区对齐（Stripe created vs 我方 createtime，样本 4 条）")
cols, rows = query("""SELECT invoiceid, createtime FROM immdata.imt_subscriptiongoodsorder
    WHERE invoiceid LIKE 'in_%' AND createtime IS NOT NULL
    ORDER BY createtime DESC LIMIT 4""")
for inv_id, ct in rows:
    st, iv, _ = get("/invoices/" + inv_id)
    if st == 200 and ct is not None:
        s_bj = bj(iv.get("created"))
        db_bj = ct.astimezone(BJ).strftime("%Y-%m-%d %H:%M:%S") if ct.tzinfo else ct.strftime("%Y-%m-%d %H:%M:%S") + "(naive)"
        print(f"  {inv_id[:26]}  Stripe(BJ)={s_bj}   DB={db_bj}")
    else:
        print(f"  {inv_id[:26]}  status={st}")

# ---- 9. 争议与退款金额量级（近 30 天，逐条求和，仅样本计数）----
section("9 退款/争议金额量级（近 30 天，最多翻 3 页 ×100）")
for res in ("refunds", "disputes"):
    total_amt, n, starting_after = 0, 0, None
    cur = None
    cur_cy = {}
    for page in range(3):
        params = {"created[gte]": since, "limit": 100}
        if starting_after:
            params["starting_after"] = starting_after
        st, body, _ = get("/" + res, params)
        if st != 200:
            break
        data = body.get("data") or []
        for obj in data:
            amt = obj.get("amount") or 0
            cy = (obj.get("currency") or "").upper()
            cur_cy[cy] = cur_cy.get(cy, 0) + amt
            total_amt += amt
            n += 1
        if body.get("has_more") and data:
            starting_after = data[-1].get("id")
        else:
            cur = False
            break
    print(f"  {res:9s}: 计数 n={n}（未翻完则更多）按币种最小单位合计 {cur_cy}")

print("\n完成。全程只发 GET；Key 未打印。")
