"""T123：Google Ads → Databend 每日无人值守同步【总入口】。

一条命令完成两件事，供定时自动化 / Windows 计划任务直接调用，无需人工干预：
  1) 从广告 URL 重新解析 campaign ↔ UTM 映射（campaign 改名自动跟上）
  2) 按账户时区回刷最近 30 天 campaign×日事实（按账号+日期窗整段替换，幂等）
  3) 库内验收：行数、最新日期、映射行数、本次台账

用法：
  F:/python312/python.exe scripts/daily_google_ads_sync.py
  F:/python312/python.exe scripts/daily_google_ads_sync.py --lookback-days 30

失败即返回非 0，便于调度报警。若 refresh_token 过期（OAuth 应用仍为 Testing
时 7 天失效），会打印明确的修复指引，不会静默跳过。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
PY = sys.executable


def run(label: str, cmd: list[str]) -> tuple[int, str]:
    print(f"\n=== {label} ===")
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    out = (p.stdout or "") + (p.stderr or "")
    print(out[-4000:])
    return p.returncode, out


TOKEN_HINT = """
⚠️ 凭证疑似失效（invalid_grant / unauthorized_client / TOKEN_EXPIRED）。
   常见原因：OAuth 同意屏幕仍是「测试 / Testing」，Google 会在 7 天后让
   refresh_token 失效。修复二选一：
   A. 在 Google Auth Platform → 目标对象，把应用发布为「正式版 / In production」
      （adwords 属敏感 scope，可能触发 Google 验证；验证通过后 token 长期有效）
   B. 保持 Testing，每 7 天重跑一次：
      F:/python312/python.exe scripts/fetch_google_ads_api.py --make-refresh-token --client-secret config/client_secret.json
   另请确认系统代理 127.0.0.1:7897 仍在运行（本机只有它能到 Google）。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=30)
    ap.add_argument("--skip-map", action="store_true")
    args = ap.parse_args()

    steps = []
    if not args.skip_map:
        steps.append(("刷新 campaign↔UTM 映射",
                      [PY, "scripts/sync_channel_campaign_map.py", "--write"]))
    steps.append(("同步 campaign×日事实",
                  [PY, "scripts/fetch_google_ads_api.py", "--sync", "--write",
                   "--lookback-days", str(args.lookback_days)]))

    for label, cmd in steps:
        rc, out = run(label, cmd)
        low = out.lower()
        if any(k in low for k in ("invalid_grant", "token_expired",
                                  "unauthorized_client", "invalid_client")):
            print(TOKEN_HINT)
        if rc != 0:
            print(f"[FAIL] {label} 退出码 {rc}；本次同步未完整完成，库内数据保持上一次成功状态")
            return rc

    # 库内验收（P019：每次自动同步都做最小自检）
    try:
        from db import query
        _, r = query("SELECT count(*), min(report_date), max(report_date) "
                     "FROM growth.google_ads_daily")
        _, m = query("SELECT count(*) FROM growth.channel_campaign_map")
        _, lg = query("SELECT count(*) FROM growth.ingest_log "
                      "WHERE source_type = 'API_SYNC'")
        rows, d0, d1 = r[0]
        print("\n=== 验收 ===")
        print(f"  growth.google_ads_daily : {rows} 行，日期 {d0} ~ {d1}")
        print(f"  growth.channel_campaign_map : {m[0][0]} 行")
        print(f"  API_SYNC 台账 : {lg[0][0]} 条")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if str(d1) < yesterday:
            print(f"  ⚠️ 最新日期 {d1} 早于昨天 {yesterday}；可能 API 数据延迟或本次未拉到新数据")
        if rows == 0 or m[0][0] == 0:
            print("  [FAIL] 事实表或映射表为空")
            return 2
        print("  [OK] 同步完成")
        return 0
    except Exception as e:
        print(f"[FAIL] 库内验收异常: {type(e).__name__}: {str(e)[:300]}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
