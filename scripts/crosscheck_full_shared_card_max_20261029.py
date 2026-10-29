import csv, ast, sys
from collections import Counter, defaultdict
sys.path.insert(0, "scripts")
from db import query

SRC = r"C:\Users\86933\Downloads\_____-2026-10-29-11-16-21 (1).csv"
LAST30 = "2026-09-29"  # 最近一个月起点（含）

# ---------- 1) 解析全量 Sigma CSV ----------
sigma_meta = {}          # fp -> meta
fp_for_sid = {}
all_sids = set()
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        fp = r["card_fingerprint"]
        sigma_meta[fp] = dict(
            brand=r["brand"], last4=r["last4"], country=r["country"],
            sigma_trial_cust=int(r["trial_customers_on_card"]),
            sigma_trial_subs=int(r["trial_subs_on_card"]),
        )
        for s in ast.literal_eval(r["subscription_ids"]):
            fp_for_sid[s] = fp
            all_sids.add(s)

sids = list(all_sids)
print(f"Sigma 全量命中卡数(>=2账号共用): {len(sigma_meta)}")
print(f"去重 farm subscription 数:        {len(sids)}")

# ---------- 2) 分批查 Databend: membership/ordertype/createtime ----------
CHUNK = 2000
rows_out = []  # (sid, membership, ordertype, createtime)
for i in range(0, len(sids), CHUNK):
    batch = sids[i:i+CHUNK]
    in_list = ",".join(f"'{s}'" for s in batch)
    sql = f"""
    SELECT subscriptionid, membership, ordertype, createtime
    FROM immdata.imt_subscriptiongoodsorder
    WHERE subscriptionid IN ({in_list})
    """
    cols, rows = query(sql)
    for r in rows:
        rows_out.append(r)
    print(f"  chunk {i//CHUNK+1}: 命中 {len(rows)} 行")

# 索引
farm_max_total = 0
farm_max_last30 = 0
farm_sub_total = len(rows_out)           # 这些 farm sub 在订单表能匹配到的（应≈全部）
farm_sub_last30 = 0
# 每个卡上的 Max 试用（全量 / 近一月）
fp_max_total = Counter()
fp_max_last30 = Counter()
fp_sub_total = Counter()
fp_sub_last30 = Counter()

for sid, mem, otype, ctime in rows_out:
    fp = fp_for_sid.get(sid, "UNKNOWN")
    is_max_trial = (str(mem).lower()=="max") and ("trial" in str(otype).lower())
    is_last30 = (ctime is not None) and (str(ctime) >= LAST30)
    fp_sub_total[fp] += 1
    if is_last30:
        fp_sub_last30[fp] += 1
    if is_max_trial:
        farm_max_total += 1
        fp_max_total[fp] += 1
        if is_last30:
            farm_max_last30 += 1
            fp_max_last30[fp] += 1
    if is_last30:
        farm_sub_last30 += 1

# ---------- 3) 分母（Databend 直接聚合，已探得）----------
DEN_MAX_TOTAL = 60482
DEN_MAX_LAST30 = 4318

# ---------- 4) 输出 ----------
print("\n================ 全量（卡农场 vs 全部 Max 试用）================")
print(f"farm subscription 总数(去重, 有卡且共享): {farm_sub_total}")
print(f"  其中 Max 试用:                        {farm_max_total}")
print(f"  其中 近一月 Max 试用:                  {farm_max_last30}")
print(f"全部 Max 试用(分母, 含无卡):             {DEN_MAX_TOTAL}")
print(f"近一月 Max 试用(分母):                  {DEN_MAX_LAST30}")
print(f"\n>>> 全量占比: farm Max {farm_max_total} / 全部 Max {DEN_MAX_TOTAL} = {100.0*farm_max_total/DEN_MAX_TOTAL:.2f}%")
print(f">>> 近一月占比: farm Max(近一月) {farm_max_last30} / 近一月全部 Max {DEN_MAX_LAST30} = {100.0*farm_max_last30/DEN_MAX_LAST30:.2f}%")

# 全 tier 明细（抽样自这批 farm sub）
from collections import Counter as C2
tier = C2((str(m), str(o)) for _,m,o,_ in rows_out)
print("\nfarm subscription 的 (membership, ordertype) 明细:")
for k,v in tier.most_common():
    print(f"  {k}: {v}")

# ---------- 5) 写交付物 CSV（全量农场卡 + 近一月 Max 数）----------
report = []
for fp, meta in sigma_meta.items():
    report.append(dict(
        card_fingerprint=fp,
        max_trials_total=fp_max_total.get(fp,0),
        max_trials_last30=fp_max_last30.get(fp,0),
        sigma_trial_customers=meta["sigma_trial_cust"],
        sigma_trial_subs=meta["sigma_trial_subs"],
        brand=meta["brand"], last4=meta["last4"], country=meta["country"],
    ))
report.sort(key=lambda x: x["max_trials_total"], reverse=True)

OUT = "output/max_trial_farm_cards_full_20261029.csv"
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["card_fingerprint","max_trials_total","max_trials_last30",
        "sigma_trial_customers","sigma_trial_subs","brand","last4","country"])
    w.writeheader()
    for r in report:
        w.writerow(r)
print(f"\n交付物写出: {OUT}  ({len(report)} 张卡)")

n_cards_max_ge2 = sum(1 for r in report if r["max_trials_total"]>=2)
n_cards_max30_ge2 = sum(1 for r in report if r["max_trials_last30"]>=2)
print(f"含>=2 全量Max试用的卡: {n_cards_max_ge2}")
print(f"含>=2 近一月Max试用的卡: {n_cards_max30_ge2}")
print(f"\nTop 15 (全量Max试用数):")
print(f"{'fp':<22}{'Max全量':>8}{'Max近月':>8}{'卡总试用':>9} {'brand':<9}{'last4':<6}{'country':<8}")
for r in report[:15]:
    print(f"{r['card_fingerprint']:<22}{r['max_trials_total']:>8}{r['max_trials_last30']:>8}{r['sigma_trial_customers']:>9} {str(r['brand']):<9}{str(r['last4']):<6}{str(r['country']):<8}")
