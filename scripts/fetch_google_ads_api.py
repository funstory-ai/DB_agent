"""T119：Google Ads API -> Databend growth.google_ads_daily（真正的 API producer）。

2026-11-16 已首次连通：`--check` 实测账户 4623896831 为 MCC 经理账号，
   其下 4 个启用子账号（CNY / Asia/Shanghai）才是数据所在。
   凭证在 config/google-ads.yaml（含 login_customer_id 指向 MCC），不进 git。
   ⚠️ 本机环境注入的代理常不可用，脚本启动时会先自动探测可达出口。

命令：
  # 0) 一次性拿 refresh_token（需先在 GCP 建 OAuth 桌面客户端并下载 client_secret.json）
  F:/python312/python.exe scripts/fetch_google_ads_api.py --make-refresh-token --client-secret <path>

  # 1) 连通性 + 枚举账户里【实际】有哪些资源/指标/账号（回答「里面有什么数据」）
  F:/python312/python.exe scripts/fetch_google_ads_api.py --check
  F:/python312/python.exe scripts/fetch_google_ads_api.py --discover

  # 2) 拉近 7 天 campaign×日：先 dry-run 对账，再入库
  F:/python312/python.exe scripts/fetch_google_ads_api.py --fetch
  F:/python312/python.exe scripts/fetch_google_ads_api.py --fetch --write

凭证：config/google-ads.yaml（模板 google-ads.yaml.example，不进 git）。
新流程（2026-09-09 后）不需要 developer_token；访问级别由**生成 OAuth 凭证的 GCP 项目**决定。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 客户端装在项目内 .vendor（全局 pip 升级依赖会被环境拦截），优先级放最前
_VENDOR = ROOT / ".vendor"
if _VENDOR.exists() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

CONFIG = ROOT / "config" / "google-ads.yaml"
CUSTOMER_ID = "4623896831"          # 界面 462-389-6831
API_VERSION = "v26"                  # 当前主版本；v22 已 2026-10-07 停用
DEFAULT_START, DEFAULT_END = "2026-11-09", "2026-11-15"

_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
               "GRPC_PROXY", "grpc_proxy")


def _registry_proxy() -> str | None:
    """读 Windows 系统代理（环境注入的代理常常是坏的，系统代理才是真实出口）。"""
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        if not winreg.QueryValueEx(k, "ProxyEnable")[0]:
            return None
        s = winreg.QueryValueEx(k, "ProxyServer")[0].strip()
        if "=" in s:  # 形如 http=host:port;https=host:port
            parts = dict(p.split("=", 1) for p in s.split(";") if "=" in p)
            s = parts.get("https") or parts.get("http") or ""
        if not s:
            return None
        return s if "://" in s else "http://" + s
    except Exception:
        return None


def _proxy_reachable(proxy: str | None) -> bool:
    """GET token 端点：能拿到 HTTP 状态码（400/403/404/405 都算）就说明链路通。"""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings()
        s = requests.Session()
        s.trust_env = False
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        r = s.get("https://oauth2.googleapis.com/token", timeout=6)
        return r.status_code in (400, 401, 403, 404, 405)
    except Exception:
        return False


def _apply_proxy(proxy: str) -> None:
    for k in _PROXY_KEYS:
        os.environ[k] = proxy
    # 本地 OAuth 回调不能被代理；同时 gRPC 也读 no_proxy
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = "localhost,127.0.0.1,::1"


def setup_network(explicit: str | None = None, force_direct: bool = False) -> None:
    """选择真正能到达 Google 的出口。

    实测 2026-11-16：环境注入 HTTP(S)_PROXY=http://127.0.0.1:59139 不可用
    （Tunnel connection failed: 502），直连超时，只有系统代理 127.0.0.1:7897 通。
    requests(oauthlib 换 token) 与 gRPC(GoogleAdsClient) 都依赖这些环境变量，
    所以在任何 API 调用之前统一修正，避免「浏览器授权成功但换 token 失败」。
    """
    if force_direct:
        for k in _PROXY_KEYS + ("ALL_PROXY", "all_proxy"):
            os.environ.pop(k, None)
        print("[NET] 强制直连（已清除代理环境变量）")
        return
    candidates = []
    if explicit:
        candidates.append(explicit)
    else:
        env_px = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if env_px:
            candidates.append(env_px)
        reg = _registry_proxy()
        if reg and reg not in candidates:
            candidates.append(reg)
    for px in candidates:
        if _proxy_reachable(px):
            _apply_proxy(px)
            print(f"[NET] 使用代理 {px}")
            return
    if _proxy_reachable(None):
        for k in _PROXY_KEYS + ("ALL_PROXY", "all_proxy"):
            os.environ.pop(k, None)
        print("[NET] 直连可用（已清除坏代理）")
        return
    print("[NET] ! 没有可达出口，保持原有设置；后续调用可能失败")


def need_client():
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        raise SystemExit(
            "缺少 google-ads 客户端：F:/python312/python.exe -m pip install google-ads"
        )
    if not CONFIG.exists():
        raise SystemExit(
            f"缺少凭证文件 {CONFIG}。请复制 config/google-ads.yaml.example 并填入 "
            "client_id / client_secret / refresh_token（不需要 developer_token）。\n"
            "没有凭证时我无法看到账户里的任何数据，也不会假装看到。"
        )
    return GoogleAdsClient.load_from_storage(str(CONFIG), version=API_VERSION)


def make_refresh_token(client_secret: str) -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit("缺少依赖：F:/python312/python.exe -m pip install google-auth-oauthlib")
    # GCP 下载的 client_secret JSON 里就带着 client_id / client_secret，一并列出来，
    # 用户不必手工翻 JSON：三个 KEY 一次给全，直接粘进 config/google-ads.yaml。
    try:
        raw = json.loads(Path(client_secret).read_text(encoding="utf-8"))
        oauth = raw.get("installed") or raw.get("web") or {}
        cid, csec = oauth.get("client_id", ""), oauth.get("client_secret", "")
    except Exception as e:
        cid, csec = "", ""
        print(f"! 读取 client_secret JSON 失败（{e}）；client_id/client_secret 需手工从文件里找")
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret, scopes=["https://www.googleapis.com/auth/adwords"]
    )
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "未拿到 refresh_token。请确认授权用的是对广告账号有读权限的 Google 账号，"
            "并在同意屏幕保持 prompt=consent 后重试。"
        )
    if not cid or not csec:
        raise SystemExit("client_secret JSON 里缺 client_id / client_secret，无法生成配置文件")

    # 凭证直接落盘，不在终端/对话里打印明文（含 refresh_token）
    import re
    tpl = ROOT / "config" / "google-ads.yaml.example"
    text = tpl.read_text(encoding="utf-8") if tpl.exists() else (
        'client_id: ""\nclient_secret: ""\nrefresh_token: ""\nuse_proto_plus: true\n'
    )
    for key, val in (("client_id", cid), ("client_secret", csec),
                     ("refresh_token", creds.refresh_token)):
        text = re.sub(rf"(?m)^{key}:.*$", f"{key}: {json.dumps(val)}", text)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(text, encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"[OK] 授权成功，3 个 KEY 已直接写入 {CONFIG.relative_to(ROOT)}（未打印明文）")
    print(f"     client_id 尾段 ...{cid[-24:]} | refresh_token 长度 {len(creds.refresh_token)}")
    print("     若通过 MCC 经理账号访问，再取消注释并填 login_customer_id。")
    print("下一步：--check → --discover → --fetch --write")
    print("=" * 60 + "\n")


def field_catalog(client) -> dict:
    """官方 GoogleAdsFieldService：按 API 版本列出可用资源/指标/细分。"""
    svc = client.get_service("GoogleAdsFieldService")
    req = client.get_type("SearchGoogleAdsFieldsRequest")
    out: dict = {"resources": [], "metrics": [], "segments": [], "campaign_meta": None}
    for label, query in [
        ("resources", "SELECT name, metrics, segments, attribute_resources WHERE category = 'RESOURCE'"),
        ("metrics", "SELECT name WHERE category = 'METRIC'"),
        ("segments", "SELECT name WHERE category = 'SEGMENT'"),
        ("campaign_meta", "SELECT name, metrics, segments, attribute_resources WHERE name = 'campaign'"),
    ]:
        req.query = query
        req.page_size = 10000
        rows = list(svc.search_google_ads_fields(request=req).results)
        if label == "campaign_meta":
            if rows:
                f = rows[0]
                out[label] = {
                    "metrics": list(f.metrics),
                    "segments": list(f.segments),
                    "attribute_resources": list(f.attribute_resources),
                }
        else:
            out[label] = [
                {"name": f.name, "n_metrics": len(f.metrics), "n_segments": len(f.segments)}
                for f in rows
            ]
    return out


def account_tree(client, customer_id: str) -> list[dict]:
    """枚举 MCC 下的账号树。实测 4623896831 是经理账号，自身 campaign=0，
    数据全在 level=1 的子账号；不枚举会拉到空表。"""
    ga = client.get_service("GoogleAdsService")
    q = ("SELECT customer_client.id, customer_client.descriptive_name, "
         "customer_client.manager, customer_client.level, customer_client.status, "
         "customer_client.currency_code, customer_client.time_zone "
         "FROM customer_client WHERE customer_client.level <= 3 "
         "ORDER BY customer_client.level, customer_client.id")
    out = []
    for batch in ga.search_stream(customer_id=customer_id, query=q):
        for r in batch.results:
            c = r.customer_client
            out.append({
                "id": str(c.id), "name": c.descriptive_name,
                "manager": bool(c.manager), "level": int(c.level),
                "status": c.status.name, "currency_code": c.currency_code,
                "time_zone": c.time_zone,
            })
    return out


def account_facts(client, customer_id: str) -> dict:
    """账户专属事实：可访问账号、账号树、实际 campaign 清单（每个账号单独查）。

    币种/时区一律取 API 实测值，禁止写死 USD / Asia/Shanghai（P045）。
    """
    facts: dict = {"customer_id": customer_id, "accessible_customers": []}
    cs = client.get_service("CustomerService")
    facts["accessible_customers"] = list(cs.list_accessible_customers().resource_names)

    ga = client.get_service("GoogleAdsService")
    stream = ga.search_stream(
        customer_id=customer_id,
        query="SELECT customer.id, customer.descriptive_name, "
              "customer.currency_code, customer.time_zone, customer.manager FROM customer",
    )
    for batch in stream:
        for r in batch.results:
            facts.update({
                "descriptive_name": r.customer.descriptive_name,
                "currency_code": r.customer.currency_code,
                "time_zone": r.customer.time_zone,
                "is_manager": r.customer.manager,
            })

    tree = account_tree(client, customer_id)
    facts["account_tree"] = tree
    leaves = [a for a in tree
              if not a["manager"] and a["status"] == "ENABLED" and a["id"] != customer_id]
    if not facts.get("is_manager"):   # 非 MCC：直接查自己
        leaves = [{"id": customer_id, "name": facts.get("descriptive_name", ""),
                   "currency_code": facts.get("currency_code", ""),
                   "time_zone": facts.get("time_zone", ""), "status": "ENABLED"}]
    facts["leaf_accounts"] = leaves

    camps = []
    for a in leaves:
        q = ("SELECT campaign.id, campaign.name, campaign.status, "
             "campaign.advertising_channel_type FROM campaign ORDER BY campaign.name")
        for batch in ga.search_stream(customer_id=a["id"], query=q):
            for r in batch.results:
                camps.append({
                    "customer_id": a["id"], "account_name": a["name"],
                    "currency_code": a["currency_code"], "time_zone": a["time_zone"],
                    "id": str(r.campaign.id), "name": r.campaign.name,
                    "status": r.campaign.status.name,
                    "channel_type": r.campaign.advertising_channel_type.name,
                })
    facts["campaigns"] = camps
    facts["campaign_count"] = len(camps)
    return facts


def do_check() -> None:
    client = need_client()
    facts = account_facts(client, CUSTOMER_ID)
    print("[CHECK] 凭证可用，API 连通")
    print("  可访问账号:", facts["accessible_customers"])
    print("  账户:", facts.get("descriptive_name"), "| 币种:", facts.get("currency_code"),
          "| 时区:", facts.get("time_zone"), "| 经理账号:", facts.get("is_manager"))
    print(f"  ⚠️ 经理账号自身通常 campaign=0，数据在其下 {len(facts['leaf_accounts'])} 个启用子账号：")
    for a in facts["leaf_accounts"]:
        print(f"    {a['id']}  {a['name']}  [{a['currency_code']} / {a['time_zone']}]")
    print("  广告系列数（全部启用子账号合计）:", facts["campaign_count"])


def do_discover() -> None:
    client = need_client()
    print("[DISCOVER] 账户专属事实 + 官方字段目录（这才是「里面有什么数据」的答案）")
    facts = account_facts(client, CUSTOMER_ID)
    catalog = field_catalog(client)
    print("\n[账户]")
    for k in ("customer_id", "descriptive_name", "currency_code", "time_zone",
              "is_manager", "campaign_count", "accessible_customers"):
        print(f"  {k}: {facts.get(k)}")
    print("\n[账号树]（status / 币种 / 时区，金额一律按子账号本币）")
    for a in facts["account_tree"]:
        print(f"  L{a['level']} {a['id']}  manager={a['manager']}  {a['status']:<9} "
              f"{a['currency_code']:<4} {a['time_zone']:<16} {a['name']}")
    print("\n[广告系列清单] （用于填 growth.channel_campaign_map，禁止猜值）")
    for c in facts["campaigns"][:120]:
        print(f"  {c['customer_id']} {c['id']:>12}  {c['status']:<10} "
              f"{c['channel_type']:<20} {c['name']}")
    print("\n[字段目录 v26]")
    print(f"  RESOURCE {len(catalog['resources'])} 个 / METRIC {len(catalog['metrics'])} 个 / SEGMENT {len(catalog['segments'])} 个")
    cm = catalog.get("campaign_meta") or {}
    print(f"  campaign 可配指标 {len(cm.get('metrics', []))} 个，含: "
          + ", ".join(cm.get("metrics", [])[:18]))
    print(f"  campaign 可配细分 {len(cm.get('segments', []))} 个，含: "
          + ", ".join(cm.get("segments", [])[:12]))
    out = ROOT / "output" / "google_ads" / f"discover_{date.today():%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"facts": facts, "catalog": catalog}, ensure_ascii=False,
                              indent=2, default=str), encoding="utf-8")
    print(f"\n  明细已存 {out.relative_to(ROOT)}")


GAQL_CAMPAIGN_DAILY = """SELECT
  segments.date, campaign.id, campaign.name,
  metrics.clicks, metrics.impressions, metrics.cost_micros,
  metrics.average_cpc, metrics.conversions, metrics.conversions_value
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND campaign.status != 'REMOVED'
ORDER BY segments.date, campaign.name"""


def do_fetch(args) -> None:
    client = need_client()
    ga = client.get_service("GoogleAdsService")
    # 账号清单、币种、时区全部来自 API 实测，不写死（P045）
    facts = account_facts(client, CUSTOMER_ID)
    leaves = facts["leaf_accounts"]
    if args.customer_id:
        wanted = {x.strip() for x in args.customer_id.split(",")}
        leaves = [a for a in leaves if a["id"] in wanted]
        missing = wanted - {a["id"] for a in leaves}
        if missing:
            print("  ! 这些账号不在启用子账号清单里（或已停用）:", sorted(missing))
        if not leaves:
            raise SystemExit("没有可拉数的账号，已停止（不会写空批次）")

    print(f"[FETCH] {args.start} ~ {args.end}，遍历 {len(leaves)} 个启用子账号（campaign×日）")
    per_account = []
    for a in leaves:
        cid = a["id"]
        q = GAQL_CAMPAIGN_DAILY.format(start=args.start, end=args.end)
        rows = []
        for batch in ga.search_stream(customer_id=cid, query=q):
            for r in batch.results:
                rows.append({
                    "report_date": datetime.strptime(r.segments.date, "%Y-%m-%d").date(),
                    "campaign_id": str(r.campaign.id),
                    "campaign_name": r.campaign.name,
                    "clicks": int(r.metrics.clicks),
                    "impressions": int(r.metrics.impressions),
                    # API 金额一律 micros，÷1e6 才是该账户本币
                    "cost_amount": Decimal(r.metrics.cost_micros) / Decimal(1_000_000),
                    "average_cpc": Decimal(r.metrics.average_cpc) / Decimal(1_000_000),
                    "conv_count": Decimal(str(r.metrics.conversions)),
                    "conv_value": Decimal(str(r.metrics.conversions_value)),
                    "ad_group_id": "", "ad_group_name": "", "keyword_text": "",
                })
        c = sum(r["clicks"] for r in rows)
        i = sum(r["impressions"] for r in rows)
        cost = sum((r["cost_amount"] for r in rows), Decimal("0"))
        print(f"  [{cid}] {a['name']} [{a['currency_code']}/{a['time_zone']}]: "
              f"{len(rows)} 行 | 点击 {c} | 展示 {i} | 花费 {cost}")
        if rows:
            per_account.append((a, rows))

    clicks = sum(r["clicks"] for _, rs in per_account for r in rs)
    impressions = sum(r["impressions"] for _, rs in per_account for r in rs)
    by_ccy: dict = {}
    for a, rs in per_account:
        by_ccy[a["currency_code"]] = by_ccy.get(a["currency_code"], Decimal("0")) + sum(
            (r["cost_amount"] for r in rs), Decimal("0")
        )
    print(f"  合计: {sum(len(rs) for _, rs in per_account)} 行 / 点击 {clicks} / 展示 {impressions}")
    print("  花费按账户本币分列:", {k: str(v) for k, v in by_ccy.items()})
    if len(by_ccy) > 1:
        print("  ⚠️ 多币种，金额禁止直接相加；与 MCC 界面 USD 汇总对比需另取汇率")
    if facts.get("currency_code") and any(k != facts["currency_code"] for k in by_ccy):
        print(f"  ⚠️ MCC 层币种 {facts['currency_code']} 与子账号本币不同：界面金额是折算值，"
              "库内存本币原值，不要直接拿界面 $ 数对账")
    if args.expect_clicks and clicks != args.expect_clicks:
        print(f"  ! 点击 {clicks} ≠ 界面 {args.expect_clicks}，请核对过滤条件与账户时区")
    if not per_account:
        print("  窗口内无数据，未产生任何写入")
        return
    if not args.write:
        print("\n[DRY-RUN] 未写库。确认后加 --write")
        return

    import ingest_google_ads_csv as ing
    base = args.batch or f"API_{args.start}_{args.end}"
    for a, rows in per_account:
        ns = argparse.Namespace(
            granularity="CAMPAIGN", customer_id=a["id"],
            currency=a["currency_code"], timezone=a["time_zone"],
            metric_flags="clicks,impressions,cost_amount,average_cpc,conv_count,conv_value",
            source_type="API",
            source_file=f"GAQL:{API_VERSION}:{a['id']}:{args.start}:{args.end}",
            note=args.note,
        )
        s = ing.summarize(rows)
        ing.write_db(rows, ns, f"{base}_{a['id']}", s)


def fetch_campaign_rows(ga, account: dict, start: str, end: str) -> list[dict]:
    """单个子账号的 campaign×日事实；金额 micros ÷ 1e6，币种/时区由调用方取实测值。"""
    q = GAQL_CAMPAIGN_DAILY.format(start=start, end=end)
    rows = []
    for batch in ga.search_stream(customer_id=account["id"], query=q):
        for r in batch.results:
            rows.append({
                "report_date": datetime.strptime(r.segments.date, "%Y-%m-%d").date(),
                "campaign_id": str(r.campaign.id),
                "campaign_name": r.campaign.name,
                "clicks": int(r.metrics.clicks),
                "impressions": int(r.metrics.impressions),
                "cost_amount": Decimal(r.metrics.cost_micros) / Decimal(1_000_000),
                "average_cpc": Decimal(r.metrics.average_cpc) / Decimal(1_000_000),
                "conv_count": Decimal(str(r.metrics.conversions)),
                "conv_value": Decimal(str(r.metrics.conversions_value)),
                "ad_group_id": "", "ad_group_name": "", "keyword_text": "",
            })
    return rows


def do_sync(args) -> int:
    """无人值守每日同步：滚动回刷窗口 + 按 (账号, 日期窗) 整段替换，重跑幂等。

    窗口＝账户时区「昨天」往前 lookback_days 天。Google Ads 转化有归因延迟，
    回刷能让历史日数据被后续转化更新；窗口外已入库的历史行保留不动。
    失败账号跳过且**不改动库内该账号数据**，整体返回非 0 便于调度报警。
    """
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    client = need_client()
    ga = client.get_service("GoogleAdsService")
    facts = account_facts(client, CUSTOMER_ID)
    leaves = facts["leaf_accounts"]
    if args.customer_id:
        wanted = {x.strip() for x in args.customer_id.split(",")}
        leaves = [a for a in leaves if a["id"] in wanted]
    if not leaves:
        raise SystemExit("没有可同步的启用子账号")

    tzname = (leaves[0].get("time_zone") or "Asia/Shanghai").strip()
    try:
        today = datetime.now(ZoneInfo(tzname)).date()
    except Exception:
        today = date.today()
    end_d = (datetime.strptime(args.sync_end, "%Y-%m-%d").date()
             if args.sync_end else today - timedelta(days=1))
    start_d = end_d - timedelta(days=args.lookback_days - 1)
    start, end = start_d.isoformat(), end_d.isoformat()

    print(f"[SYNC] 窗口 {start} ~ {end}（回刷 {args.lookback_days} 天，账户时区 {tzname}）"
          f"，账号 {len(leaves)} 个；source=API_SYNC")
    import ingest_google_ads_csv as ing
    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    failed, ok = [], 0
    for a in leaves:
        cid = a["id"]
        # 只删本账号本窗口内、同粒度的事实行（不限来源批次），避免与历史批次重复累计
        scope = (f"customer_id = '{cid}' AND granularity = 'CAMPAIGN' "
                 f"AND report_date BETWEEN '{start}' AND '{end}'")
        try:
            rows = fetch_campaign_rows(ga, a, start, end)
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"  [{cid}] 拉取失败，跳过且不改动库内该账号数据 → {msg}")
            failed.append((cid, msg))
            continue
        clicks = sum(r["clicks"] for r in rows)
        print(f"  [{cid}] {a['name']}: {len(rows)} 行 / 点击 {clicks}")
        if not args.write:
            ok += 1
            continue
        if rows:
            ns = argparse.Namespace(
                granularity="CAMPAIGN", customer_id=cid,
                currency=a["currency_code"], timezone=a["time_zone"],
                metric_flags="clicks,impressions,cost_amount,average_cpc,conv_count,conv_value",
                source_type="API_SYNC",
                source_file=f"GAQL:{API_VERSION}:{cid}:{start}:{end}",
                note=f"auto-sync lookback={args.lookback_days}",
            )
            ing.write_db(rows, ns, f"SYNC_{cid}_{run_tag}",
                         ing.summarize(rows), replace_scope=scope)
        else:
            import db_writer as w
            w.execute("DELETE FROM growth.google_ads_daily WHERE " + scope)
            print(f"  [{cid}] 窗口内 0 行，已清理该窗口旧数据（不写空台账）")
        ok += 1

    if args.write:
        from db import query
        _, r = query("SELECT count(*), min(report_date), max(report_date) "
                     "FROM growth.google_ads_daily")
        print(f"[SYNC] 库内现有 {r[0][0]} 行，日期 {r[0][1]} ~ {r[0][2]}")
    print(f"[SYNC] 完成 {ok}/{len(leaves)} 个账号，失败 {len(failed)}")
    for cid, msg in failed:
        print(f"  FAIL {cid}: {msg}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--sync", action="store_true",
                    help="无人值守同步：自动算回刷窗口，按账号+日期窗整段替换（幂等）")
    ap.add_argument("--make-refresh-token", action="store_true")
    ap.add_argument("--client-secret")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--sync-end", default="",
                    help="[sync] 截止日 YYYY-MM-DD；默认＝账户时区的昨天")
    ap.add_argument("--lookback-days", type=int, default=30,
                    help="[sync] 回刷天数，默认 30（覆盖 Google Ads 转化归因延迟）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--batch", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--customer-id", default="",
                    help="只拉指定子账号（逗号分隔）；默认遍历 MCC 下所有启用子账号")
    ap.add_argument("--currency", default="USD", help="[已废弃] 币种由 API 实测取，不再手工指定")
    ap.add_argument("--timezone", default="", help="[已废弃] 时区由 API 实测取，不再手工指定")
    ap.add_argument("--expect-clicks", type=int)
    ap.add_argument("--proxy", default="", help="显式指定代理，如 http://127.0.0.1:7897")
    ap.add_argument("--no-proxy", action="store_true", help="强制直连，忽略所有代理")
    args = ap.parse_args()

    # 必须在任何 requests / gRPC 调用之前修正出口，否则换 token 会 502
    setup_network(args.proxy or None, args.no_proxy)

    if args.make_refresh_token:
        if not args.client_secret:
            raise SystemExit("需要 --client-secret <GCP OAuth 客户端 JSON 路径>")
        make_refresh_token(args.client_secret)
    elif args.check:
        do_check()
    elif args.discover:
        do_discover()
    elif args.sync:
        return do_sync(args)
    elif args.fetch:
        do_fetch(args)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
