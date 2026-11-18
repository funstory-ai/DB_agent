"""T123：Google Ads 账户【实际数据资产】盘点（API 实测，不是官方通用字段清单）。

目的（用户 2026-11-16 14:25）：第一次用后台，需要知道「里面到底有哪些数据」，
并据此自行判断「结合 immdata 看不同渠道转化率」这个最终目标能不能做。

★ 11-16 实测重大发现：广告的 final_urls / final_url_suffix 里带我方 UTM 参数，
  utm_campaign = googlekeywords_pdf_translate / googlekeywords_website_translate_*
  等，与 immdata.imt_campaigninfo.utmcampaign 完全同一套命名。
  ⇒ growth.channel_campaign_map 可由数据自动推导，不必猜中文投放名（P045）。
  本脚本额外输出 campaign_utm（广告系列 → UTM campaign 的实测对应）。

用法：
  F:/python312/python.exe scripts/inventory_google_ads.py
  F:/python312/python.exe scripts/inventory_google_ads.py --probe-days 30 --history-start 2023-01-01

输出：output/google_ads/inventory_YYYYMMDD.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_google_ads_api as f  # noqa: E402  (复用 setup_network / account_tree)

# key, 中文说明, GAQL, 是否插日期窗口
PROBES = [
    ("history_daily", "账户日汇总（最早/最晚有数据日期、历史可回溯范围）",
     "SELECT segments.date, metrics.clicks, metrics.impressions, metrics.cost_micros "
     "FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}' "
     "ORDER BY segments.date", True),

    ("customer_config", "账户配置（币种/时区/自动标记/跟踪模板）",
     "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
     "customer.time_zone, customer.auto_tagging_enabled, "
     "customer.tracking_url_template, customer.final_url_suffix FROM customer", False),

    # v26 实测：campaign 没有 start_date / end_date 字段（那在 campaign_budget 等别处）
    ("campaign_config", "广告系列配置（含 URL 后缀 / 跟踪模板 / 出价策略）",
     "SELECT campaign.id, campaign.name, campaign.status, "
     "campaign.advertising_channel_type, campaign.final_url_suffix, "
     "campaign.tracking_url_template, campaign.bidding_strategy_type "
     "FROM campaign ORDER BY campaign.name", False),

    ("ad_group_config", "广告组配置（含 URL 后缀）",
     "SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status, "
     "ad_group.final_url_suffix FROM ad_group ORDER BY ad_group.id", False),

    ("ad_final_urls", "广告最终到达网址（UTM 来源，含所属 campaign）",
     "SELECT campaign.id, campaign.name, ad_group.id, ad_group_ad.ad.id, "
     "ad_group_ad.ad.name, ad_group_ad.ad.final_urls, "
     "ad_group_ad.ad.final_url_suffix, ad_group_ad.ad.tracking_url_template "
     "FROM ad_group_ad", False),

    ("expanded_landing_page", "展开后的落地页 URL（含 ValueTrack 展开值）",
     "SELECT segments.date, expanded_landing_page_view.expanded_final_url, "
     "metrics.clicks, metrics.impressions FROM expanded_landing_page_view "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    # v26 实测：字段名是 unexpanded_final_url，不是 landing_page_url
    ("landing_page", "落地页 URL（未展开）",
     "SELECT segments.date, landing_page_view.unexpanded_final_url, metrics.clicks "
     "FROM landing_page_view WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    ("keyword", "关键词维度（词、匹配方式、点击/花费）",
     "SELECT segments.date, campaign.id, ad_group.id, "
     "ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
     "ad_group_criterion.keyword.match_type, ad_group_criterion.final_url_suffix, "
     "metrics.clicks, metrics.impressions, metrics.cost_micros "
     "FROM keyword_view WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    ("search_term", "用户实际搜索词",
     "SELECT segments.date, search_term_view.search_term, search_term_view.status, "
     "metrics.clicks, metrics.impressions FROM search_term_view "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    ("geographic", "地域维度（国家/地区 criterion）",
     "SELECT segments.date, geographic_view.country_criterion_id, "
     "geographic_view.location_type, metrics.clicks FROM geographic_view "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    ("device_network", "设备 × 广告网络细分",
     "SELECT segments.date, segments.device, segments.ad_network_type, "
     "metrics.clicks, metrics.impressions FROM campaign "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    # v26 实测：attribution_model_settings 不可 SELECT
    ("conversion_action", "转化动作定义（Google 自归因口径）",
     "SELECT conversion_action.id, conversion_action.name, conversion_action.type, "
     "conversion_action.status, conversion_action.category FROM conversion_action", False),

    ("conversion_by_day", "账户级转化指标（conversions / value）",
     "SELECT segments.date, metrics.conversions, metrics.conversions_value, "
     "metrics.all_conversions FROM customer "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),

    # v26 实测：ClickView 必须限定单日
    ("click_view", "点击级 GCLID（用户级归因键，需单日过滤）",
     "SELECT segments.date, click_view.gclid, click_view.ad_group_ad, "
     "click_view.page_number FROM click_view WHERE segments.date = '{end}'", True),

    ("ad_group_daily", "广告组 × 日事实（更细粒度是否有数据）",
     "SELECT segments.date, ad_group.id, ad_group.name, metrics.clicks, "
     "metrics.impressions, metrics.cost_micros FROM ad_group "
     "WHERE segments.date BETWEEN '{start}' AND '{end}'", True),
]

URL_FIELDS = ("final_urls", "final_url_suffix", "tracking_url_template",
              "unexpanded_final_url", "expanded_final_url")


def get_path(obj, path: str):
    cur = obj
    for p in path.split("."):
        if cur is None:
            return None
        try:
            cur = getattr(cur, p)
        except AttributeError:
            return None
    if cur is not None and "Enum" in str(type(cur)) and hasattr(cur, "name"):
        try:
            return cur.name
        except Exception:
            pass
    if cur is not None and ("Repeated" in type(cur).__name__ or isinstance(cur, (list, tuple))):
        try:
            return list(cur)
        except Exception:
            pass
    if isinstance(cur, (str, int, float, bool)) or cur is None:
        return cur
    return str(cur)


def fields_of(query: str) -> list[str]:
    s = query.strip()
    low = s.lower()
    a = low.find("select ") + len("select ")
    b = low.find(" from ")
    return [x.strip() for x in s[a:b].split(",") if x.strip()]


def utm_from(value) -> dict:
    """从 URL / URL 后缀里抽 utm_* / gclid / keyword 等参数。"""
    out: dict[str, set] = {}
    vals = value if isinstance(value, (list, tuple)) else [value]
    for v in vals:
        if not v or not isinstance(v, str):
            continue
        q = parse_qs(urlparse(v).query, keep_blank_values=False)
        if not q and ("utm_" in v or "gclid" in v):
            q = parse_qs(v.lstrip("?&"), keep_blank_values=False)
        for k, vs in q.items():
            kl = k.lower()
            if kl.startswith("utm_") or kl in ("gclid", "keyword", "matchtype", "creative",
                                               "network", "adposition", "campaignid", "adgroupid"):
                out.setdefault(kl, set()).update(vs)
    return {k: sorted(v) for k, v in out.items()}


def row_dict(row, fields: list[str]) -> dict:
    return {fld: get_path(row, fld) for fld in fields}


def probe_one(ga, cid: str, key: str, label: str, query: str,
              has_date: bool, start: str, end: str, sample_n: int = 3) -> dict:
    q = query.format(start=start, end=end)
    fields = fields_of(q)
    res: dict = {"label": label, "ok": False, "gaql": q, "fields": fields}
    rows, dates = [], []
    utm: dict[str, Counter] = {}
    value_counts: dict[str, Counter] = {}
    campaign_utm: dict[str, Counter] = defaultdict(Counter)
    campaign_urls: dict[str, Counter] = defaultdict(Counter)
    try:
        for batch in ga.search_stream(customer_id=cid, query=q):
            for r in batch.results:
                d = row_dict(r, fields)
                rows.append(d)
                dv = d.get("segments.date")
                if dv:
                    dates.append(str(dv))
                camp = d.get("campaign.name") or d.get("campaign.id")
                for fk, fv in d.items():
                    if any(fk.endswith(x) for x in URL_FIELDS):
                        u = utm_from(fv)
                        for k, vs in u.items():
                            utm.setdefault(k, Counter()).update(vs)
                        if camp:
                            for uc in u.get("utm_campaign", []):
                                campaign_utm[str(camp)][uc] += 1
                            raw = fv if isinstance(fv, str) else "|".join(fv or [])
                            if raw:
                                campaign_urls[str(camp)][raw[:220]] += 1
                    if fk in ("segments.device", "segments.ad_network_type",
                              "ad_group_criterion.keyword.match_type",
                              "geographic_view.location_type",
                              "conversion_action.type", "conversion_action.category",
                              "campaign.bidding_strategy_type") and fv:
                        value_counts.setdefault(fk, Counter())[str(fv)] += 1
        res.update({
            "ok": True,
            "row_count": len(rows),
            "date_min": min(dates) if dates else None,
            "date_max": max(dates) if dates else None,
            "distinct_dates": len(set(dates)) if dates else 0,
            "sample": rows[:sample_n],
            "utm": {k: dict(v) for k, v in utm.items()},
            "value_distribution": {k: dict(v) for k, v in value_counts.items()},
            "campaign_utm": {k: dict(v) for k, v in campaign_utm.items()},
            "campaign_urls": {k: dict(v) for k, v in campaign_urls.items()},
        })
    except Exception as e:
        err = str(e)
        try:
            fail = getattr(e, "failure", None)
            if fail and fail.errors:
                err = " | ".join(x.message for x in fail.errors[:2])
        except Exception:
            pass
        res["error"] = err[:600]
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-days", type=int, default=30)
    ap.add_argument("--history-start", default="2023-01-01")
    ap.add_argument("--end-date", default="", help="截止日 YYYY-MM-DD，默认昨天")
    ap.add_argument("--accounts", default="", help="只探查指定子账号（逗号分隔）")
    ap.add_argument("--skip-history", action="store_true")
    ap.add_argument("--proxy", default="")
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    f.setup_network(args.proxy or None, args.no_proxy)
    client = f.need_client()
    ga = client.get_service("GoogleAdsService")

    tree = f.account_tree(client, f.CUSTOMER_ID)
    accounts = [a for a in tree if not a["manager"] and a["status"] == "ENABLED"]
    if args.accounts:
        wanted = {x.strip() for x in args.accounts.split(",")}
        accounts = [a for a in accounts if a["id"] in wanted]
    end = args.end_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    probe_start = (datetime.strptime(end, "%Y-%m-%d")
                   - timedelta(days=args.probe_days - 1)).strftime("%Y-%m-%d")

    print(f"[INVENTORY] 探查窗口 {probe_start} ~ {end}（{args.probe_days} 天）；"
          f"历史起点 {args.history_start}；账号 {len(accounts)} 个")
    out: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "login_customer_id": f.CUSTOMER_ID,
        "api_version": f.API_VERSION,
        "windows": {"probe": [probe_start, end], "history": [args.history_start, end]},
        "account_tree": tree, "accounts": {}, "errors": [],
    }

    for a in accounts:
        cid = a["id"]
        print(f"\n=== {cid} {a['name']} [{a['currency_code']} / {a['time_zone']}] ===")
        acc: dict = {"info": a, "probes": {}}
        for key, label, query, has_date in PROBES:
            if key == "history_daily" and args.skip_history:
                continue
            start = args.history_start if key == "history_daily" else probe_start
            r = probe_one(ga, cid, key, label, query, has_date, start, end)
            acc["probes"][key] = r
            if r["ok"]:
                extra = ""
                if r.get("utm"):
                    extra = "  UTM=" + ",".join(f"{k}:{len(v)}" for k, v in r["utm"].items())
                print(f"  {key:<24} rows={r['row_count']:>7}  "
                      f"dates={r['date_min']}~{r['date_max']}{extra}")
            else:
                print(f"  {key:<24} ERR {r.get('error','')[:110]}")
                out["errors"].append({"account": cid, "probe": key,
                                     "error": r.get("error", "")})
        out["accounts"][cid] = acc

    summary: dict = {
        "available_probes": {},
        "utm_campaign_values": set(), "utm_source_values": set(),
        "utm_medium_values": set(), "total_history": {},
        "campaign_utm_map": {}, "errors": len(out["errors"]),
    }
    for cid, acc in out["accounts"].items():
        for k, r in acc["probes"].items():
            if not r["ok"]:
                continue
            s = summary["available_probes"].setdefault(k, {"accounts": [], "rows": 0})
            if r["row_count"]:
                s["accounts"].append(cid)
                s["rows"] += r["row_count"]
            for field, vals in (r.get("utm") or {}).items():
                if field in ("utm_campaign", "utm_source", "utm_medium"):
                    summary[field + "_values"].update(vals)
            for camp, ucs in (r.get("campaign_utm") or {}).items():
                tgt = summary["campaign_utm_map"].setdefault(camp, {})
                for uc, n in ucs.items():
                    tgt[uc] = tgt.get(uc, 0) + n
        h = acc["probes"].get("history_daily") or {}
        if h.get("ok") and h.get("row_count"):
            summary["total_history"][cid] = {
                "date_min": h["date_min"], "date_max": h["date_max"],
                "distinct_dates": h["distinct_dates"], "rows": h["row_count"],
            }
    for k in ("utm_campaign_values", "utm_source_values", "utm_medium_values"):
        summary[k] = sorted(summary[k])
    out["summary"] = summary

    dest = ROOT / "output" / "google_ads" / f"inventory_{datetime.now():%Y%m%d}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    print("\n[SUMMARY] 可用资源（有数据的账号数 / 行数）:")
    for k, v in summary["available_probes"].items():
        print(f"  {k:<24} {len(v['accounts'])} 个账号 / {v['rows']} 行")
    print("\n[★ campaign → UTM 实测映射]（自动建 channel_campaign_map 的依据）")
    for camp, ucs in sorted(summary["campaign_utm_map"].items()):
        print(f"  {camp}  →  {', '.join(sorted(ucs))}")
    print("\n  UTM source 取值:", summary["utm_source_values"][:25])
    print("  UTM medium 取值:", summary["utm_medium_values"][:15])
    print("  历史可回溯:", summary["total_history"])
    print(f"  失败 probe 数: {summary['errors']}")
    print(f"\n  明细已存 {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
