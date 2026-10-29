import csv

# 成本单价（USD / 百万 token）
# pro-token: T068 验收值（实际 capture 加权） $0.33/1M
PRO_PRICE = 0.33
# 顶级 token: 供应商价表 terra/gpt-5.4 (in 1.5~1.6, out 9~9.6)，按 83:17 混合 ≈ $2.9/1M（估算，未单独验收）
TOP_PRICE = 2.9
FX = 7.1  # USD->CNY 粗略折算（标注假设）

TOP_PER = 100_000     # 每 Max 试用 顶级 token
PRO_PER = 1_000_000   # 每 Max 试用 pro token

rows = []
with open(r"H:/databend_sql/output/max_trial_farm_cards_full_20261029.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append(r)

def s(x):
    try: return int(x)
    except: return 0

n_cards = len(rows)
mt_total = sum(s(r["max_trials_total"]) for r in rows)
mt_last30 = sum(s(r["max_trials_last30"]) for r in rows)
sig_subs = sum(s(r["sigma_trial_subs"]) for r in rows)        # 全 tier 共享卡试用
sig_cust = sum(s(r["sigma_trial_customers"]) for r in rows)    # 全 tier 共享账号

# 全量 Max 试用分母（之前交叉复核结果）
DEN_TOTAL = 60_482
DEN_LAST30 = 4_318

print(f"共享农场卡张数: {n_cards}")
print(f"农场卡 Max 试用(全量): {mt_total}  | 占全部 Max 试用 {DEN_TOTAL}: {mt_total/DEN_TOTAL*100:.1f}%")
print(f"农场卡 Max 试用(近30天): {mt_last30} | 占近30天 Max 试用 {DEN_LAST30}: {mt_last30/DEN_LAST30*100:.1f}%")
print(f"(对照) 共享卡全 tier 试用: {sig_subs} 单 / {sig_cust} 账号")
print()

for label, n in [("全量", mt_total), ("近30天", mt_last30)]:
    top_tok = n * TOP_PER
    pro_tok = n * PRO_PER
    cost_top = top_tok / 1e6 * TOP_PRICE
    cost_pro = pro_tok / 1e6 * PRO_PRICE
    cost_usd = cost_top + cost_pro
    cost_cny = cost_usd * FX
    print(f"== {label} 农场卡 Max 试用 {n} 个 ==")
    print(f"  顶级 token: {top_tok/1e6:.1f}M  -> ${cost_top:,.0f}")
    print(f"  pro  token: {pro_tok/1e6:.1f}M  -> ${cost_pro:,.0f}")
    print(f"  合计成本(额度用满上限): ${cost_usd:,.0f}  ≈ ¥{cost_cny:,.0f}")
    print()

print("说明: 这是按'试用额度用满'估计的上限成本(给的额度×模型成本价)。")
print(f"实际成本=这些账号真实用量×成本价, 应低于上限。pro=${PRO_PRICE}/1M(验收); 顶级=${TOP_PRICE}/1M(按供应商价表估算)。")
