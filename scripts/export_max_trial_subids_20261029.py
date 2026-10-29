"""导出 Max 试用的 Stripe subscriptionid 全集（给 Stripe Sigma Query B 用）。

只读查询，复用 scripts/db.py 的连接封装。
口径（P013）：finished + amountpaid=0 + 非兑换码 + membership='max'。
这是"全部试用"，不是≥N次。
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

from db import query

OUT = Path(__file__).resolve().parents[1] / "output" / "max_trial_subscriptionids_20261029.csv"

SQL = """
SELECT
  subscriptionid,
  userid,
  ordertype,
  useremail,
  createtime
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0
  AND orderstatus='finished'
  AND COALESCE(amountpaid,0)=0
  AND LOWER(ordertype) NOT IN ('code')   -- 排除兑换码（P013）
  AND membership='max'
  AND subscriptionid IS NOT NULL
ORDER BY userid, createtime
"""


def q(sql: str, retries: int = 6):
    """带指数退避重试（覆盖 OSS AccessDenied 等瞬态）。"""
    last = None
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(2 ** i)
    raise last


def main() -> None:
    cols, rows = q(SQL)
    print("columns:", cols)
    print("total rows (trial orders with sub id):", len(rows))

    # 去重统计 distinct subscriptionid
    subs = {r[0] for r in rows}
    users = {r[1] for r in rows}
    print("distinct subscriptionid:", len(subs))
    print("distinct userid:", len(users))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print("written ->", OUT)

    # 同时产出一个仅含 distinct subscriptionid 的单列文件，方便粘进 Sigma IN()
    single = OUT.with_name("max_trial_subids_distinct_20261029.txt")
    with single.open("w", encoding="utf-8") as f:
        for s in sorted(subs):
            f.write(f"{s}\n")
    print("distinct ids ->", single)


if __name__ == "__main__":
    main()
