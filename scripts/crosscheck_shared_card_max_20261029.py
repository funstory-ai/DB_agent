import csv, ast, sys
sys.path.insert(0, "scripts")
from db import query

SRC = r"C:\Users\86933\Downloads\_____-2026-10-29-11-16-21.csv"

# 1) 从 Sigma CSV 抽取全部 subscription_id 及其卡 fingerprint
sids = set()
fp_for_sid = {}
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        for s in ast.literal_eval(r["subscription_ids"]):
            sids.add(s)
            fp_for_sid[s] = r["card_fingerprint"]
sids = list(sids)
print(f"Sigma 共享卡涉及 subscription 数(去重): {len(sids)}")

in_list = ",".join(f"'{s}'" for s in sids)

# 2) Databend: (membership, ordertype) 分布
sql = f"""
SELECT membership, ordertype,
       COUNT(*) AS orders,
       COUNT(DISTINCT userid) AS users,
       COUNT(DISTINCT subscriptionid) AS subs
FROM immdata.imt_subscriptiongoodsorder
WHERE subscriptionid IN ({in_list})
GROUP BY membership, ordertype
ORDER BY orders DESC
"""
cols, rows = query(sql)
print("\n=== Databend 交叉验证：(membership, ordertype) 分布 ===")
print(" | ".join(cols))
for r in rows:
    print(" | ".join(str(x) for x in r))

# 3) Max 试用计数
sql2 = f"""
SELECT COUNT(*) AS max_trial_orders,
       COUNT(DISTINCT userid) AS max_trial_users,
       COUNT(DISTINCT subscriptionid) AS max_trial_subs
FROM immdata.imt_subscriptiongoodsorder
WHERE subscriptionid IN ({in_list})
  AND lower(membership) = 'max'
  AND lower(ordertype) LIKE '%trial%'
"""
cols2, rows2 = query(sql2)
print("\n=== 其中为 Max 试用的部分 ===")
print(" | ".join(cols2))
for r in rows2:
    print(" | ".join(str(x) for x in r))

# 4) 拉回 Max 试用的 subscriptionid，反推卡分布
sql3 = f"""
SELECT subscriptionid
FROM immdata.imt_subscriptiongoodsorder
WHERE subscriptionid IN ({in_list})
  AND lower(membership) = 'max'
  AND lower(ordertype) LIKE '%trial%'
"""
cols3, rows3 = query(sql3)
max_sids = set(r[0] for r in rows3)

from collections import Counter
fp_counter = Counter()
for s in max_sids:
    fp_counter[fp_for_sid.get(s, "UNKNOWN")] += 1

rows_fp = [(fp, c) for fp, c in fp_counter.items() if c >= 2]
rows_fp.sort(key=lambda x: x[1], reverse=True)
print(f"\n=== 涉及 Max 试用的共享卡（>=2 个 Max 试用）===")
print(f"涉及 Max 试用的卡数: {len(fp_counter)} ; 其中>=2的卡: {len(rows_fp)} ; Max试用总数(在这些卡上): {sum(c for _,c in rows_fp)}")
print(f"{'fp':<22}{'Max试用数':>10}")
for fp, c in rows_fp[:40]:
    print(f"{fp:<22}{c:>10}")
