# -*- coding: utf-8 -*-
"""T125 验证：分语言地区付费转化率 SQL 口径核对。
用 6 月窗口跑用户给的两条 SQL，看能否复现 datapack 2026.06 快照：
  简中 月活3966611 / 订阅34491 / 付费率0.008695；繁中 305422/8366；英语 136232/1678...
只读 SELECT。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# datapack 2026.06 基准
BASE = {
    'zh-CN': (3966611, 34491), 'zh-TW': (305422, 8366), 'en': (136232, 1678),
    'ko': (40677, 1461), 'ja': (22004, 507), 'ar': (29098, 186),
    'fr': (14487, 83), 'de': (5311, 71), 'es': (21160, 126),
}

LANGS = "'zh-CN','zh-TW','ko','en','ja','ar','fr','de','es'"

def active_sql(y0, m0, y1, m1):
    # 月活：target_language 去重设备，translate_page 事件，版本排除 1.11.4
    return f"""
select t0.target_language, count(distinct t1.device_id) as mau
from (
  select * from immdata.imt_device_regional_test
  where target_language in ({LANGS})
) t0
left join (
  select * from immdata.user_behaviour
  where created_ts >= '{y0}-{m0:02d}-01'
    and created_ts <  '{y1}-{m1:02d}-01'
    and event_name = 'translate_page'
    and version != '1.11.4'
) t1 on t0.device_id = t1.device_id
group by t0.target_language
"""

def paid_sql(month_end, next_first):
    # 月末仍有效的付费订阅 userid（按设备最新语言归属）
    return f"""
select tt1.target_language, count(distinct tt2.userid) as paid
from (
  select * from (
    select *, row_number() over (partition by userid order by t0.created_ts desc) rn
    from (
      select * from immdata.imt_device_regional_test
      where target_language in ({LANGS})
    ) t0
    left join immdata.imt_deviceinfo t1 on t0.device_id = t1.deviceid
  ) where rn = 1
) tt1
left join immdata.imt_subscriptiongoodsorder tt2 on tt1.userid = tt2.userid
where tt2.amountpaid > 0
  and tt2.orderstatus = 'finished'
  and date_add(day, subscriptionday, tt2.createtime) >= '{month_end}'
  and tt2.createtime <= '{next_first}'
group by tt1.target_language
"""

def run(label, sql):
    print('='*60, label)
    try:
        cols, rows = query(sql)
        print('cols', cols)
        for r in rows:
            print(' ', r)
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        print(' ERROR', type(e).__name__, str(e)[:500])
        return {}

if __name__ == '__main__':
    print('=== 6月窗口验证（用户SQL口径）===')
    # datapack 2026.06 = 月活6月 + 付费截止6月末
    mau6 = run('MAU 2026-06', active_sql(2026, 6, 2026, 7))
    paid6 = run('PAID asof 2026-06-30', paid_sql('2026-06-30', '2026-07-01'))
    print('\n=== 对比 datapack 2026.06 基准 ===')
    for lang,(bm,bp) in BASE.items():
        print(f'{lang:6s} base mau={bm:>9} paid={bp:>7} | got mau={mau6.get(lang)} paid={paid6.get(lang)}')
