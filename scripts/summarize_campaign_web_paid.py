"""T115: aggregate the two recorded query snapshots, without exposing identifiers."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/campaign_web_paid'
CAMPAIGNS = ['homepage', 'message_2611_sale', 'pricing_activity_modal', 'ad_banner_2026_1111']
PLANS = ['pro_month', 'pro_year', 'max_month', 'max_year']
CLICK_PLANS = {'month': 'pro_month', 'year': 'pro_year', 'maxMonth': 'max_month', 'maxYear': 'max_year'}
ORDER_PLANS = {'monthly': 'pro_month', 'yearly': 'pro_year', 'max_monthly': 'max_month', 'max_yearly': 'max_year'}

def read(name):
    d = json.loads((OUT / name).read_text())
    return d, [dict(zip(d['columns'], r)) for r in d['rows']]

def logged(r):
    return bool(r['login_userid'] and r['login_userid'] > 0)

event_source, events = read('events.json')
order_source, orders = read('orders.json')
visits = [r for r in events if r['event_name'] == 'official_page_view' and r['site_host'] == 'immersivetranslate.com']
clicks = [r for r in events if r['event_name'] == 'pricing_purchase_btn_click']
paid = [r for r in orders if r['is_paid']]
assert all(r['fingerprint'] for r in visits)
assert all(r['click_plan'] in CLICK_PLANS for r in clicks)
assert all(r['subscriptiontype'] in ORDER_PLANS for r in paid)
assert len({r['order_id'] for r in paid}) == len(paid)
assert all(r['order_userid'] == r['checkout_userid'] for r in paid)
assert all(r['source_rows'] == 1 for r in orders)

def summarize(c=None):
    v = [r for r in visits if c is None or r['campaign'] == c]
    cl = [r for r in clicks if c is None or r['trigger'] == c]
    o = [r for r in orders if c is None or r['campaign'] == c]
    p = [r for r in paid if c is None or r['campaign'] == c]
    plans_click = Counter(CLICK_PLANS[r['click_plan']] for r in cl)
    plans_paid = Counter(ORDER_PLANS[r['subscriptiontype']] for r in p)
    anon = [r for r in v if not logged(r)]
    login = [r for r in v if logged(r)]
    return {
        'campaign': c or 'all', 'pv': len(v), 'pv_anonymous': len(anon), 'pv_logged': len(login),
        'fingerprint_uv': len({r['fingerprint'] for r in v}),
        'fingerprint_uv_anonymous': len({r['fingerprint'] for r in anon}),
        'fingerprint_uv_logged': len({r['fingerprint'] for r in login}),
        'logged_accounts': len({r['login_userid'] for r in login}),
        'clicks': len(cl), 'clicks_anonymous': sum(not logged(r) for r in cl),
        'clicks_logged': sum(logged(r) for r in cl),
        'click_logged_accounts': len({r['login_userid'] for r in cl if logged(r)}),
        'click_plans': {k: plans_click[k] for k in PLANS},
        'checkouts': len({r['checkout_id'] for r in o}),
        'checkout_accounts': len({r['checkout_userid'] for r in o}),
        'trial_orders': len({r['order_id'] for r in o if r['is_trial']}),
        'paid_orders': len(p), 'paid_accounts': len({r['order_userid'] for r in p}),
        'paid_plans': {k: plans_paid[k] for k in PLANS},
        'paid_order_types': dict(Counter(r['ordertype'] for r in p)),
        'refunded_orders_excluded': sum(r['orderstatus'] == 'refunded' for r in o),
        'first_visit_utc': min((r['created_ts'] for r in v), default=None),
        'last_visit_utc': max((r['created_ts'] for r in v), default=None),
    }

summary = {
    'beijing_period': '[2026-10-28 00:00:00, 2026-11-13 00:00:00)',
    'source_executions': {'events': event_source['executed_at_utc'], 'orders': order_source['executed_at_utc']},
    'scope': 'Production official site immersivetranslate.com; all paths carrying the campaign',
    'identity': 'PV login state from event login_userid; UV is distinct nonempty fingerprint, separately by state',
    'attribution': 'Latest source snapshot campaign -> exact checkout -> exact paid order checkoutsessionid; checkout and order both in period',
    'excluded_hosts': dict(Counter(r['site_host'] for r in events if r['event_name'] == 'official_page_view' and r['site_host'] != 'immersivetranslate.com')),
    'campaigns': [summarize(c) for c in CAMPAIGNS], 'total': summarize(),
}
assert summary['total']['pv'] == sum(r['pv'] for r in summary['campaigns'])
assert summary['total']['clicks'] == sum(r['clicks'] for r in summary['campaigns'])
assert summary['total']['paid_orders'] == sum(r['paid_orders'] for r in summary['campaigns'])
assert all(sum(r['click_plans'].values()) == r['clicks'] and sum(r['paid_plans'].values()) == r['paid_orders'] for r in summary['campaigns'])
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
