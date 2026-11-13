# -*- coding: utf-8 -*-
"""wf —— 需求生命周期状态机（失败即拒）。

设计哲学（搬运自 opencode-workhard 的 control-plane）：
  - 状态在模型之外持久化（SQLite），不因上下文压缩丢失；
  - 非法状态转换由代码抛错拒绝，不靠模型自觉；
  - "完成"只能由 `audit` 这唯一权威判定，"看起来做完了"的散文不算。

阶段顺序（只能前进，不能跳级）：
  briefed -> caliber(口径) -> queried(写SQL) -> sampled(抽样复核) -> delivered(交付) -> audited(验收)

门禁规则（fail-closed）：
  - deliver 必须已过 sampled（没抽样不准交付）；
  - sampled 必须已填 `## 口径` 与 `## 抽样复核`；
  - 导出脚本启动时调用 wf.require(TID, 'sampled')，未过门直接退出。

用法：
  python scripts/wf.py open   T108 --cat query --title "..." [--doc docs/tasks/xxx.md]
  python scripts/wf.py caliber T108
  python scripts/wf.py sampled T108
  python scripts/wf.py deliver T108
  python scripts/wf.py audit   T108
  python scripts/wf.py require T108 sampled      # 给导出脚本用，过不了会非零退出
  python scripts/wf.py check   T108              # 打印 PASS/FAIL 明细
  python scripts/wf.py list
  python scripts/wf.py status  T108
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / ".workbuddy" / "workflow" / "runtime.db"
TASKS_DIR = REPO / "docs" / "tasks"

STAGES = ["briefed", "caliber", "queried", "sampled", "delivered", "audited"]


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB))
    c.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            category TEXT,
            title TEXT,
            doc_path TEXT,
            stage TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )"""
    )
    return c


def _now() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get(task_id: str) -> dict | None:
    c = _conn()
    try:
        row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    finally:
        c.close()
    if not row:
        return None
    cols = ["task_id", "category", "title", "doc_path", "stage", "created_at", "updated_at"]
    return dict(zip(cols, row))


def _set_stage(task_id: str, stage: str) -> None:
    c = _conn()
    try:
        c.execute(
            "UPDATE tasks SET stage=?, updated_at=? WHERE task_id=?",
            (stage, _now(), task_id),
        )
        c.commit()
    finally:
        c.close()


# ---------- 文档章节占位检测 ----------
def _read_doc(doc_path: str | None) -> str | None:
    if not doc_path:
        return None
    p = Path(doc_path)
    if not p.is_absolute():
        p = REPO / doc_path
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str | None:
    """返回 ## heading 到下一个 ## 之间的内容；找不到返回 None。

    匹配标题前缀（兼容 `## 口径（正式交付）` 这类带后缀的标题），
    但要求 heading 后紧跟行尾/空白/括号，避免 `## 口径确认` 被误判为 `口径`。
    """
    m = re.search(r"^##\s+" + re.escape(heading) + r"(?:$|[\s（(])", text, re.M)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"^##\s+", text[start:], re.M)
    return text[start : start + nxt.start()] if nxt else text[start:]


def _caliber_filled(section: str) -> bool:
    """口径已填：模板里 `时间窗` 永远是空值，真实口径必填它。"""
    # 找到 "时间窗" 所在行的定义列
    m = re.search(r"\|\s*时间窗\s*\|([^|]*)\|", section)
    if not m:
        return False
    return m.group(1).strip() != ""


def _sampled_filled(section: str) -> bool:
    s = section.strip()
    if not s:
        return False
    # 模板占位只是这一句
    if s.startswith("（P019") or s.startswith("(P019"):
        return False
    return len(s) > 15


def _coverage_filled(section: str) -> bool:
    # 需求覆盖对照：必须至少有一行非表头/分隔行有内容
    rows = [l for l in section.splitlines() if l.strip().startswith("|")]
    if len(rows) < 3:
        return False
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if any(cells):
            return True
    return False


# ---------- 阶段推进 ----------
def _advance(task_id: str, target: str, need_doc_check: bool = False) -> None:
    rec = _get(task_id)
    if not rec:
        die(f"[{task_id}] 不存在。先 `wf open {task_id}`。")
    cur = rec["stage"]
    # 交付/验收的显式硬校验：必须已过 sampled
    if target in ("delivered", "audited") and STAGES.index(cur) < STAGES.index("sampled"):
        die(f"[{task_id}] 不能 {target}：必须先过 sampled（当前={cur}）。")
    if STAGES.index(target) < STAGES.index(cur):
        die(f"[{task_id}] 不能回退到 {target}（当前已是 {cur}）。")
    if STAGES.index(target) > STAGES.index(cur) + 1:
        die(f"[{task_id}] 不能跳级到 {target}（当前 {cur}，须顺序推进）。")
    if need_doc_check:
        doc = _read_doc(rec["doc_path"])
        if doc is None:
            die(f"[{task_id}] 找不到任务文档（doc_path={rec['doc_path']}），无法校验口径/抽样。")
        if target == "caliber" and not _caliber_filled(_section(doc, "口径") or ""):
            die(f"[{task_id}] `## 口径` 未填（时间窗为空）——先写清口径再 mark caliber。")
        if target == "sampled":
            if not _caliber_filled(_section(doc, "口径") or ""):
                die(f"[{task_id}] `## 口径` 未填，不能进入 sampled。")
            if not _sampled_filled(_section(doc, "抽样复核") or ""):
                die(f"[{task_id}] `## 抽样复核` 仍是模板占位——先完成 P019 抽样再 mark sampled。")
    _set_stage(task_id, target)
    print(f"[{task_id}] stage -> {target}")


def die(msg: str, code: int = 2) -> None:
    print("WF-GATE: " + msg, file=sys.stderr)
    sys.exit(code)


# ---------- 公开 API（给导出脚本 import） ----------
def require(task_id: str, stage: str) -> None:
    """导出脚本启动时调用：未达 stage 直接非零退出（fail-closed）。"""
    rec = _get(task_id)
    if not rec:
        die(f"[{task_id}] 未在建状态机中（先 `wf open {task_id}`）。")
    if STAGES.index(rec["stage"]) < STAGES.index(stage):
        die(f"[{task_id}] 交付门禁未过：需要 stage>={stage}，当前={rec['stage']}。"
            f"先完成口径声明与抽样复核（wf caliber / wf sampled）。")


def get_stage(task_id: str) -> str | None:
    rec = _get(task_id)
    return rec["stage"] if rec else None


# ---------- 子命令 ----------
def cmd_open(a):
    c = _conn()
    try:
        exist = c.execute("SELECT 1 FROM tasks WHERE task_id=?", (a.task_id,)).fetchone()
        if exist:
            die(f"[{a.task_id}] 已存在。")
        doc = a.doc or str(TASKS_DIR / f"{a.task_id}.md")
        c.execute(
            "INSERT INTO tasks(task_id,category,title,doc_path,stage,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (a.task_id, a.cat, a.title, doc, "briefed", _now(), _now()),
        )
        c.commit()
    finally:
        c.close()
    print(f"[{a.task_id}] opened -> briefed  (doc={doc})")


def cmd_mark(a):
    need = a.stage in ("caliber", "sampled")
    _advance(a.task_id, a.stage, need_doc_check=need)


def cmd_require(a):
    require(a.task_id, a.stage)


def cmd_check(a):
    rec = _get(a.task_id)
    if not rec:
        die(f"[{a.task_id}] 不存在。")
    doc = _read_doc(rec["doc_path"])
    if not doc:
        print(f"[{a.task_id}] FAIL: 找不到文档 {rec['doc_path']}")
        sys.exit(1)
    checks = {
        "口径(时间窗)": _caliber_filled(_section(doc, "口径") or ""),
        "需求覆盖对照": _coverage_filled(_section(doc, "需求覆盖对照") or ""),
        "抽样复核": _sampled_filled(_section(doc, "抽样复核") or ""),
    }
    ok = all(checks.values())
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"[{a.task_id}] stage={rec['stage']}  -> {'ALL PASS' if ok else 'GATE NOT MET'}")
    sys.exit(0 if ok else 1)


def cmd_list(a):
    c = _conn()
    try:
        rows = c.execute("SELECT task_id,category,stage,title,updated_at FROM tasks ORDER BY task_id").fetchall()
    finally:
        c.close()
    if not rows:
        print("(no tasks)")
        return
    for r in rows:
        print(f"  {r[0]:8} {r[1]:8} {r[2]:9} {r[4]}  {r[3]}")


def cmd_status(a):
    rec = _get(a.task_id)
    if not rec:
        die(f"[{a.task_id}] 不存在。")
    print(f"[{a.task_id}] stage={rec['stage']}  cat={rec['category']}  doc={rec['doc_path']}")
    print(f"  进度: {' '.join('✔' if STAGES.index(s) <= STAGES.index(rec['stage']) else '·' for s in STAGES)}")
    print(f"        {' '.join(STAGES)}")


def build_parser():
    p = argparse.ArgumentParser(prog="wf", description="需求生命周期状态机（失败即拒）")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open", help="新建需求（briefed）")
    o.add_argument("task_id")
    o.add_argument("--cat", required=True)
    o.add_argument("--title", default="")
    o.add_argument("--doc", default="")
    o.set_defaults(func=cmd_open)

    m = sub.add_parser("caliber", help="标记口径已填（校验文档）")
    m.add_argument("task_id")
    m.set_defaults(func=cmd_mark, stage="caliber")
    m = sub.add_parser("queried", help="标记 SQL 已写")
    m.add_argument("task_id"); m.set_defaults(func=cmd_mark, stage="queried")
    m = sub.add_parser("sampled", help="标记抽样复核完成（校验文档）")
    m.add_argument("task_id"); m.set_defaults(func=cmd_mark, stage="sampled")
    m = sub.add_parser("deliver", help="标记已交付（需 sampled）")
    m.add_argument("task_id"); m.set_defaults(func=cmd_mark, stage="delivered")
    m = sub.add_parser("audit", help="标记已验收（唯一完成权威，需 sampled）")
    m.add_argument("task_id"); m.set_defaults(func=cmd_mark, stage="audited")

    r = sub.add_parser("require", help="给导出脚本：未达 stage 则非零退出")
    r.add_argument("task_id"); r.add_argument("stage"); r.set_defaults(func=cmd_require)

    ck = sub.add_parser("check", help="打印口径/抽样 PASS-FAIL 明细")
    ck.add_argument("task_id"); ck.set_defaults(func=cmd_check)

    sub.add_parser("list", help="列出所有需求").set_defaults(func=cmd_list)
    s = sub.add_parser("status", help="查看单任务进度")
    s.add_argument("task_id"); s.set_defaults(func=cmd_status)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
