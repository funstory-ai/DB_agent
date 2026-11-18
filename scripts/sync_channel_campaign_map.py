"""T123：从 Google Ads 广告 URL 自动解析 campaign ↔ UTM 映射，写入 growth.channel_campaign_map。

⚠️ 解决的是 11-16 早先「中文投放名与 googlekeywords_* 对不上、只能人工猜」的死结：
   实测广告的 final_urls / final_url_suffix / tracking_url_template 里就带 utm_campaign，
   且与我方 imt_campaigninfo.utmcampaign 是同一套命名。
   ⇒ 映射由 API 数据推导（P045 合规），不是人工猜值。

幂等：先清空映射表再整表重写；每次运行重新从 API 拉取，campaign 改名会自动跟上。
用法：
  F:/python312/python.exe scripts/sync_channel_campaign_map.py           # dry-run
  F:/python312/python.exe scripts/sync_channel_campaign_map.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_google_ads_api as f  # noqa: E402

AD_GAQL = ("SELECT campaign.id, campaign.name, ad_group_ad.ad.id, "
           "ad_group_ad.ad.final_urls, ad_group_ad.ad.final_url_suffix, "
           "ad_group_ad.ad.tracking_url_template FROM ad_group_ad")
CAMP_GAQL = ("SELECT campaign.id, campaign.name, campaign.final_url_suffix, "
             "campaign.tracking_url_template FROM campaign")


def params_of(value: str | None) -> dict[str, list[str]]:
    if not value:
        return {}
    q = parse_qs(urlparse(value).query, keep_blank_values=False)
    if not q and ("utm_" in value or "gclid" in value):
        q = parse_qs(value.lstrip("?&"), keep_blank_values=False)
    return {k.lower(): v for k, v in q.items()}


def first(p: dict, key: str) -> str:
    v = p.get(key) or []
    if not v:
        return ""
    return (v[0] or "").strip()


def channel_group(uc: str, us: str, um: str) -> str:
    """渠道大类：由实测 UTM 值规则化，规则写在这里便于复核，不写死单条记录。

    顺序有讲究：先看 UTM campaign 前缀（我方 SEM 命名），再看 KOL/YouTube，
    再看 display，最后才按 utm_source=google 兜底 —— 否则展示广告会被误并进 google_sem。
    """
    c, s, m = uc.lower(), us.lower(), um.lower()
    if c.startswith("googlekeywords_") or s == "googlesem":
        return "google_sem"
    if s in ("youtube", "youtu.be") or "youtube" in s:
        return "youtube_kol"
    if m == "display" or "display" in c or "video" in c.lower():
        return "display_video"
    if s == "google" and "search" in m:
        return "google_sem"
    if s:
        return "other_paid"
    return "unattributed"


def collect(client) -> tuple[list[dict], list[dict], dict]:
    ga = client.get_service("GoogleAdsService")
    tree = f.account_tree(client, f.CUSTOMER_ID)
    accounts = [a for a in tree if not a["manager"] and a["status"] == "ENABLED"]
    pairs: dict[tuple, dict] = {}
    no_utm: dict[str, int] = defaultdict(int)
    per_account: dict[str, dict] = {}

    for a in accounts:
        cid = a["id"]
        seen = 0
        for batch in ga.search_stream(customer_id=cid, query=AD_GAQL):
            for r in batch.results:
                seen += 1
                camp = str(r.campaign.name)
                ad = r.ad_group_ad.ad
                urls = list(ad.final_urls) or []
                suffixes = [str(ad.final_url_suffix or ""), str(ad.tracking_url_template or "")]
                found = False
                for u in urls:
                    p = params_of(str(u))
                    for s in suffixes:  # suffix 里的 utm_* 优先级更高（ValueTrack 常用）
                        for k, v in params_of(s).items():
                            p.setdefault(k, v)
                    uc, us, um = first(p, "utm_campaign"), first(p, "utm_source"), first(p, "utm_medium")
                    if not uc:
                        continue
                    found = True
                    key = (camp, uc, us, um)
                    rec = pairs.setdefault(key, {
                        "ads_campaign_name": camp, "utm_campaign": uc,
                        "utm_source": us, "utm_medium": um,
                        "channel_group": channel_group(uc, us, um),
                        "accounts": set(), "url_count": 0,
                    })
                    rec["accounts"].add(cid)
                    rec["url_count"] += 1
                # 没有 final_urls 但 suffix 自带完整 UTM 的情况
                if not found:
                    for s in suffixes:
                        p = params_of(s)
                        uc, us, um = first(p, "utm_campaign"), first(p, "utm_source"), first(p, "utm_medium")
                        if not uc:
                            continue
                        found = True
                        key = (camp, uc, us, um)
                        rec = pairs.setdefault(key, {
                            "ads_campaign_name": camp, "utm_campaign": uc,
                            "utm_source": us, "utm_medium": um,
                            "channel_group": channel_group(uc, us, um),
                            "accounts": set(), "url_count": 0,
                        })
                        rec["accounts"].add(cid)
                        rec["url_count"] += 1
                if not found:
                    no_utm[camp] += 1
        # campaign 级 suffix 兜底
        for batch in ga.search_stream(customer_id=cid, query=CAMP_GAQL):
            for r in batch.results:
                p = params_of(str(r.campaign.final_url_suffix or ""))
                for k, v in params_of(str(r.campaign.tracking_url_template or "")).items():
                    p.setdefault(k, v)
                uc, us, um = first(p, "utm_campaign"), first(p, "utm_source"), first(p, "utm_medium")
                if not uc:
                    continue
                key = (str(r.campaign.name), uc, us, um)
                rec = pairs.setdefault(key, {
                    "ads_campaign_name": str(r.campaign.name), "utm_campaign": uc,
                    "utm_source": us, "utm_medium": um,
                    "channel_group": channel_group(uc, us, um),
                    "accounts": set(), "url_count": 0,
                })
                rec["accounts"].add(cid)
        per_account[cid] = {"name": a["name"], "ads_scanned": seen,
                            "pairs_so_far": len(pairs)}

    rows = []
    for rec in pairs.values():
        rows.append({
            "ads_campaign_name": rec["ads_campaign_name"],
            "utm_campaign": rec["utm_campaign"],
            "utm_source": rec["utm_source"],
            "utm_medium": rec["utm_medium"],
            "channel_group": rec["channel_group"],
            "accounts": sorted(rec["accounts"]),
            "url_count": rec["url_count"],
        })
    rows.sort(key=lambda x: (x["channel_group"], x["ads_campaign_name"], x["utm_campaign"]))
    meta = {"per_account": per_account,
            "campaigns_without_utm": dict(sorted(no_utm.items(), key=lambda x: -x[1]))}
    return rows, accounts, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--proxy", default="")
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    f.setup_network(args.proxy or None, args.no_proxy)
    client = f.need_client()
    rows, accounts, meta = collect(client)
    stamp = datetime.now().strftime("%Y%m%d")
    print(f"[MAP] 从 {len(accounts)} 个启用子账号的广告 URL 解析出 {len(rows)} 条 "
          f"campaign↔UTM 映射，覆盖 {len({r['ads_campaign_name'] for r in rows})} 个 campaign")
    bygroup: dict[str, int] = defaultdict(int)
    for r in rows:
        bygroup[r["channel_group"]] += 1
    print("  渠道大类分布:", dict(bygroup))
    for r in rows[:60]:
        print(f"    {r['channel_group']:<14} {r['ads_campaign_name'][:38]:<38} → "
              f"{r['utm_campaign']}  [src={r['utm_source']} med={r['utm_medium']}]")
    if meta["campaigns_without_utm"]:
        print("  ⚠️ 未从 URL 解析到 UTM 的 campaign（不写映射表，禁止猜值）:",
              list(meta["campaigns_without_utm"].items())[:12])

    dest = ROOT / "output" / "google_ads" / f"campaign_map_{stamp}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                                "rows": rows, "meta": meta}, ensure_ascii=False,
                               indent=2, default=str), encoding="utf-8")
    print(f"  明细已存 {dest.relative_to(ROOT)}")

    if not args.write:
        print("\n[DRY-RUN] 未写库。确认后加 --write")
        return 0
    import db_writer as w
    q = w.sql_quote
    w.execute("DELETE FROM growth.channel_campaign_map")
    today = datetime.now().strftime("%Y-%m-%d")
    prefix = "INSERT INTO growth.channel_campaign_map VALUES "
    for i in range(0, len(rows), 100):
        chunk = rows[i:i + 100]
        vals = []
        for r in chunk:
            note = (f"API实测URL自动解析 {stamp} acct={','.join(r['accounts'])} "
                    f"urls={r['url_count']}")
            vals.append("(" + ",".join([
                q(r["ads_campaign_name"]), q(r["utm_campaign"]), q(r["utm_source"]),
                q(r["utm_medium"]), q(r["channel_group"]), f"'{today}'",
                "'2099-12-31'", q(note),
            ]) + ")")
        w.execute(prefix + ",".join(vals))
    _, res = w.execute("SELECT count(*) FROM growth.channel_campaign_map")
    print(f"[WRITE] growth.channel_campaign_map 现有 {res[0][0]} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
