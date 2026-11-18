# -*- coding: utf-8 -*-
"""T125 正式取数：从飞书自动同步表 + immdata 拉取 Q3 全量数据，落地 JSON 供合并脚本用。
只读：飞书 GET + immdata SELECT，不写任何外部系统。
输出：output/_t125_q3_source.json
"""
from __future__ import annotations
import json, urllib.request, sys
from pathlib import Path

ROOT_FB = Path(r"H:\imt-feishu-ga-sync")
ENV = ROOT_FB / ".env"
BASE = "https://open.feishu.cn/open-apis"
OUT = Path(r"H:\databend_sql\output\_t125_q3_source.json")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query


def load_env():
    out = {}
    for raw in ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def http(method, url, token=None, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def flat(c):
    if isinstance(c, list) and c and isinstance(c[0], dict) and "text" in c[0]:
        return c[0].get("text")
    return c


def read(tok, ss, rng):
    q = urllib.request.quote(rng, safe="!:")
    r = http("GET", f"{BASE}/sheets/v2/spreadsheets/{ss}/values/{q}", token=tok)
    if r.get("code") != 0:
        raise RuntimeError(f"read {rng}: {r}")
    return [[flat(c) for c in row] for row in (r.get("data", {}).get("valueRange", {}).get("values") or [])]


LANGS = "'zh-CN','zh-TW','ko','en','ja','ar','fr','de','es'"

def region_paid(month_end, next_first):
    sql = f"""
select tt1.target_language, count(distinct tt2.userid) as paid
from (
  select * from (
    select *, row_number() over (partition by userid order by t0.created_ts desc) rn
    from (select * from immdata.imt_device_regional_test where target_language in ({LANGS})) t0
    left join immdata.imt_deviceinfo t1 on t0.device_id = t1.deviceid
  ) where rn = 1
) tt1
left join immdata.imt_subscriptiongoodsorder tt2 on tt1.userid = tt2.userid
where tt2.amountpaid > 0 and tt2.orderstatus = 'finished'
  and date_add(day, subscriptionday, tt2.createtime) >= '{month_end}'
  and tt2.createtime <= '{next_first}'
group by tt1.target_language
"""
    cols, rows = query(sql)
    return {r[0]: int(r[1]) for r in rows}


def region_active(y0, m0, y1, m1):
    sql = f"""
select t0.target_language, count(distinct t1.device_id) as mau
from (select * from immdata.imt_device_regional_test where target_language in ({LANGS})) t0
left join (
  select * from immdata.user_behaviour
  where created_ts >= '{y0}-{m0:02d}-01' and created_ts < '{y1}-{m1:02d}-01'
    and event_name = 'translate_page' and version != '1.11.4'
) t1 on t0.device_id = t1.device_id
group by t0.target_language
"""
    cols, rows = query(sql)
    return {r[0]: int(r[1]) for r in rows}


def main():
    env = load_env()
    tok = http("POST", BASE + "/auth/v3/tenant_access_token/internal",
               body={"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]})["tenant_access_token"]
    ga = env["FEISHU_SPREADSHEET_TOKEN"]
    biz = "HNiasEsDKh0YQjtqKK7cmml8nld"
    acq = "HUPNss3mSh0dcRtQKL5c3BdPnuf"
    d = {}
    # 月留存 GA：左右两块，A:S，全量
    d["月留存GA"] = read(tok, ga, "NO6Ydt!A1:S45")
    # 付费留存：上半率、下半人数、年费 O:T，全量
    d["付费留存"] = read(tok, biz, "2ZNaOH!A1:T75")
    # 同期群：A:AC
    d["同期群"] = read(tok, acq, "0eYKoD!A1:AC40")
    # ARPU：含 Q3 区块
    d["ARPU"] = read(tok, biz, "5sbtqZ!A1:F135")
    # 飞书月活表 Q3 计算值(G:E? 实际 H:M: 累计激活/调用AI/网页/PDF/EPUB/视频) + E列自建月活
    d["月活表"] = read(tok, ga, "wbiWtt!A38:M46")
    # 分语言转化率：用户 SQL 口径，Q3 主月=9月（日期随 Q3 变动）
    d["分语言_月活_202609"] = region_active(2026, 9, 2026, 10)
    d["分语言_付费_202609"] = region_paid("2026-09-30", "2026-10-01")

    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    for k, v in d.items():
        print(k, len(v) if isinstance(v, list) else v)


if __name__ == "__main__":
    main()
