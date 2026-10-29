import csv, ast, sys
from collections import Counter
sys.path.insert(0, "scripts")
from db import query

SRC = r"C:\Users\86933\Downloads\_____-2026-10-29-11-16-21.csv"

# Sigma 侧卡元数据
sigma_meta = {}   # fp -> dict(brand,last4,country,sigma_trial_cust,sigma_trial_subs)
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

in_list = ",".join(f"'{s}'" for s in all_sids)

# Databend: 每个 subscription 是否 Max 试用
sql = f"""
SELECT subscriptionid
FROM immdata.imt_subscriptiongoodsorder
WHERE subscriptionid IN ({in_list})
  AND lower(membership)='max'
  AND lower(ordertype) LIKE '%trial%'
"""
_, rows = query(sql)
max_sids = set(r[0] for r in rows)

# 反推每张卡的 Max 试用数
fp_max = Counter()
for s in max_sids:
    fp_max[fp_for_sid.get(s, "UNKNOWN")] += 1

# 组装报告：所有命中卡，标注 Max 试用数
report = []
for fp, meta in sigma_meta.items():
    mx = fp_max.get(fp, 0)
    report.append(dict(
        card_fingerprint=fp,
        max_trials=mx,
        sigma_trial_customers=meta["sigma_trial_cust"],
        sigma_trial_subs=meta["sigma_trial_subs"],
        brand=meta["brand"],
        last4=meta["last4"],
        country=meta["country"],
    ))
report.sort(key=lambda x: x["max_trials"], reverse=True)

# 写 CSV
OUT = "output/max_trial_farm_cards_20261029.csv"
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["card_fingerprint","max_trials",
        "sigma_trial_customers","sigma_trial_subs","brand","last4","country"])
    w.writeheader()
    for r in report:
        w.writerow(r)

n_cards = len(report)
n_max_cards = sum(1 for r in report if r["max_trials"] >= 2)
total_max = sum(r["max_trials"] for r in report)
print(f"报告已写出: {OUT}")
print(f"Sigma 命中卡总数(>=2账号共用): {n_cards}")
print(f"其中含>=2个Max试用的卡:        {n_max_cards}")
print(f"这些卡上的 Max 试用总数:       {total_max}")
print(f"\nTop 15 Max 农场卡:")
print(f"{'fp':<22}{'Max试用':>8}{'卡上总试用':>10} {'brand':<9}{'last4':<6}{'country':<8}")
for r in report[:15]:
    print(f"{r['card_fingerprint']:<22}{r['max_trials']:>8}{r['sigma_trial_customers']:>10} {str(r['brand']):<9}{str(r['last4']):<6}{str(r['country']):<8}")
