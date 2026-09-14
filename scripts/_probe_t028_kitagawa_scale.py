# -*- coding: utf-8 -*-
"""Lang counterfactuals + scale ladder to overall pp."""
from __future__ import annotations

# From prior queries (recent Win Chrome store)
# overall headline
OVERALL_DROP = -5.249
WIN_TOTAL_PP = -4.324  # kitagawa to overall
WIN_SHARE_AUG = 0.7893
WIN_DROP = -6.189

# Win browsers kitagawa (of win)
CHROME_MIX, CHROME_RATE = 0.889, -5.501
ELECTRON_MIX, ELECTRON_RATE = -0.136, -1.034
EDGE_MIX, EDGE_RATE = -0.846, 0.480

# chrome_store of Win Chrome late
STORE_SHARE_OF_CHROME = 0.8944
STORE_DROP = 24.13 - 32.39  # -8.26

# L3 channel buckets (of chrome_store)
ZOMBIE_PP, RECENT_PP, OTHER_PP = 1.309, -4.660, -4.986
CHANNEL_DROP = -8.338

# recent 4-cell + CFs
RECENT_DROP = -8.02
US_EN_KIT = -0.261
US_EN_CF_RATE = 1.92
US_EN_CF_SHARE = 3.47
US_EN_CF_BOTH = 4.79
US_NONEN_KIT = -2.886
EX_EN_KIT = 1.565
EX_NONEN_KIT = -6.439

# recent share of store late
RECENT_SHARE_STORE = 0.4023

# lang kitagawa
EN_KIT, ZH_KIT, OTH_KIT = 1.311, -8.284, -0.723

def to_overall_via_win_rate(pp_of_win: float) -> float:
    return WIN_SHARE_AUG * pp_of_win

def approx_store_of_overall() -> float:
    # Win * Chrome_of_Win * store_of_Chrome (late shares)
    return WIN_SHARE_AUG * 0.6243 * STORE_SHARE_OF_CHROME

print("=== Scale ladder (approx pp of OVERALL -5.25) ===")
print(f"Windows total_pp: {WIN_TOTAL_PP:.2f}")
print(f"  Chrome mix+rate of Win {(CHROME_MIX+CHROME_RATE):.2f} -> overall {to_overall_via_win_rate(CHROME_MIX+CHROME_RATE):.2f}")
print(f"  Electron -> overall {to_overall_via_win_rate(ELECTRON_MIX+ELECTRON_RATE):.2f}")
print(f"  Edge -> overall {to_overall_via_win_rate(EDGE_MIX+EDGE_RATE):.2f}")

store_of_all = approx_store_of_overall()
print(f"\nchrome_store share of overall NI (late)~ {store_of_all*100:.1f}%")
print(f"channel drop {CHANNEL_DROP:.2f}pp * share -> rough overall {store_of_all*CHANNEL_DROP:.2f}")
print(f"  recent bucket {RECENT_PP:.2f} of channel -> overall {store_of_all*RECENT_PP:.2f}")
print(f"  other_ver {OTHER_PP:.2f} -> overall {store_of_all*OTHER_PP:.2f}")
print(f"  zombie {ZOMBIE_PP:.2f} -> overall {store_of_all*ZOMBIE_PP:.2f}")

# US_en CF both recovers 4.79 of recent 8.02; recent rate_pp of channel = -3.228
recent_rate_pp_channel = -3.228
usen_frac = US_EN_CF_BOTH / abs(RECENT_DROP)
usen_to_channel = usen_frac * abs(recent_rate_pp_channel)  # positive recover
print(f"\nUS_en CF both recover {US_EN_CF_BOTH:.2f} of recent {RECENT_DROP:.2f}")
print(f"  as fraction of recent rate_pp_channel: recover ~{usen_to_channel:.2f}pp of channel")
print(f"  -> overall ~{store_of_all * usen_to_channel:.2f}pp of headline")
print(f"US_en Kitagawa only {US_EN_KIT:.2f} of recent -> overall ~{store_of_all * RECENT_SHARE_STORE * US_EN_KIT:.2f}")

# zh-CN CF approx from L4 numbers
sj = dict(en=0.3446, zh=0.4491, oth=0.2063)
sa = dict(en=0.4385, zh=0.3755, oth=0.1860)
rj = dict(en=0.3128, zh=0.7077, oth=0.4800)
ra = dict(en=0.2758, zh=0.6257, oth=0.4936)
r_aug = sum(sa[k]*ra[k] for k in sa)
# freeze zh share+rate
others = ["en", "oth"]
other_sa = sum(sa[k] for k in others)
synth = {"zh": sj["zh"]}
for k in others:
    synth[k] = (1 - sj["zh"]) * sa[k] / other_sa
rates = {"zh": rj["zh"], "en": ra["en"], "oth": ra["oth"]}
cf_zh = sum(synth[k] * rates[k] for k in synth)
print(f"\nlang recent actual~{r_aug*100:.2f}")
print(f"CF freeze zh-CN share+rate: {cf_zh*100:.2f} recover {(cf_zh-r_aug)*100:.2f}pp recent")
# freeze en
other_sa = sa["zh"] + sa["oth"]
synth = {"en": sj["en"], "zh": (1-sj["en"])*sa["zh"]/other_sa, "oth": (1-sj["en"])*sa["oth"]/other_sa}
rates = {"en": rj["en"], "zh": ra["zh"], "oth": ra["oth"]}
cf_en = sum(synth[k]*rates[k] for k in synth)
print(f"CF freeze en share+rate: {cf_en*100:.2f} recover {(cf_en-r_aug)*100:.2f}pp recent")
print(f"  en CF -> overall ~{store_of_all * (cf_en-r_aug)/abs(RECENT_DROP) * abs(recent_rate_pp_channel):.2f}")
print(f"  zh CF -> overall ~{store_of_all * (cf_zh-r_aug)/abs(RECENT_DROP) * abs(recent_rate_pp_channel):.2f}")
