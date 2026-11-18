# -*- coding: utf-8 -*-
"""T125 验证：拉取飞书自动同步表，与 datapack 现有历史值比对，确认是否原始数据源。
只读：仅 GET 飞书 values/metainfo，不写任何飞书表、不写 datapack。
"""
from __future__ import annotations
import json, urllib.request
from pathlib import Path

ROOT = Path(r"H:\imt-feishu-ga-sync")
ENV = ROOT / ".env"
BASE = "https://open.feishu.cn/open-apis"
OUT = Path(r"H:\databend_sql\output\_t125_feishu_probe.json")


def load_env():
    out = {}
    for raw in ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def http(method, url, token=None, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def flat(c):
    if isinstance(c, list) and c and isinstance(c[0], dict) and "text" in c[0]:
        return c[0].get("text")
    return c


def read(token, ss, rng):
    q = urllib.request.quote(rng, safe="!:")
    resp = http("GET", f"{BASE}/sheets/v2/spreadsheets/{ss}/values/{q}", token=token)
    if resp.get("code") != 0:
        return {"error": resp}
    return [[flat(c) for c in row] for row in (resp.get("data", {}).get("valueRange", {}).get("values") or [])]


def metainfo(token, ss):
    resp = http("GET", f"{BASE}/sheets/v2/spreadsheets/{ss}/metainfo", token=token)
    if resp.get("code") != 0:
        return []
    return [{"sheetId": s.get("sheetId"), "title": s.get("title")} for s in resp.get("data", {}).get("sheets", [])]


def main():
    env = load_env()
    tok = http("POST", f"{BASE}/auth/v3/tenant_access_token/internal",
               body={"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]})["tenant_access_token"]
    ga = env["FEISHU_SPREADSHEET_TOKEN"]           # 沉浸式GA数据
    biz = "HNiasEsDKh0YQjtqKK7cmml8nld"           # 2024商业化数据（复购/付费留存/ARPU）
    acq = "HUPNss3mSh0dcRtQKL5c3BdPnuf"           # 获客数据（同期群）

    result = {}
    # 1) 月留存 GA: NO6Ydt —— 拉全表 A:S（左侧新增+留存率，右侧人数）
    result["月留存GA_NO6Ydt"] = read(tok, ga, "NO6Ydt!A1:S60")
    # 2) 付费留存: 2ZNaOH —— 上半月费率、下半人数、年费 O:T
    result["付费留存_2ZNaOH"] = read(tok, biz, "2ZNaOH!A1:T75")
    # 3) 同期群: 0eYKoD —— A:AC
    result["同期群_0eYKoD"] = read(tok, acq, "0eYKoD!A1:AC40")
    # 4) ARPU: 5sbtqZ
    result["ARPU_5sbtqZ"] = read(tok, biz, "5sbtqZ!A1:F140")
    # 5) 分语言转化候选：获客表 cohort_language 10 张 n 表元信息
    result["获客表metainfo"] = metainfo(tok, acq)
    result["商业化表metainfo"] = metainfo(tok, biz)
    result["GA表metainfo"] = metainfo(tok, ga)

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    for k in result:
        v = result[k]
        print(k, "rows=", len(v) if isinstance(v, list) else v)


if __name__ == "__main__":
    main()
