"""T104 验证：token_used_aw.timestamp vs imm_token_used.dates 逐日一致性（排查时间戳是否 ETL 归一）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from db import query

UID = 5993459
def q(sql):
    c, r = query(sql); return c, r

print("=== A) imm_token_used 日汇总 逐日（2026-09 ~ 2026-11）===")
c, r = q(f"""SELECT to_char(dates,'%Y-%m-%d') d,
  coalesce(openai,0)+coalesce(deepl,0)+coalesce(deepseek,0)+coalesce(gemini,0)
  +coalesce(claude,0)+coalesce(bigmodel,0)+coalesce(babel_doc,0)+coalesce(qwen3,0)
  +coalesce(doubao,0)+coalesce(pics,0)+coalesce(asr_audio,0)+coalesce(comics,0)
  +coalesce(math_pix,0)+coalesce(openai_gpt_41,0)+coalesce(gemini_25_pro_preview,0)
  +coalesce(claude4,0)+coalesce(novice_ai,0)+coalesce(qwen_plus,0)+coalesce(kimi_k2_0905,0)
  +coalesce(bigmodel45air,0)+coalesce(novice_pro_pdf,0)+coalesce(novice_asr_audio,0) AS tok
FROM immdata.imm_token_used WHERE userid={UID} AND dates>='2026-09-01' AND dates<'2026-11-10'
ORDER BY 1""")
print(c)
for x in r: print(x)

print("\n=== B) token_used_aw 逐日（同窗口，看时间戳是否真的集中在少数日）===")
c, r = q(f"""SELECT to_char(timestamp,'%Y-%m-%d') d, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-10 00:00:00'
GROUP BY 1 ORDER BY 1""")
print(c)
for x in r: print(x)

print("\n=== C) token_used_aw 各月 不同 timestamp 日期数 ===")
c, r = q(f"""SELECT to_char(timestamp,'%Y-%m') ym, count(DISTINCT to_char(timestamp,'%Y-%m-%d')) distinct_days, count(*) n
FROM immdata.token_used_aw WHERE userid={UID} AND recordtype='capture'
  AND timestamp>='2026-05-01 00:00:00' AND timestamp<'2026-11-10 00:00:00'
GROUP BY 1 ORDER BY 1""")
print(c)
for x in r: print(x)
