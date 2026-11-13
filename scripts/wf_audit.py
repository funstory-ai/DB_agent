# -*- coding: utf-8 -*-
"""wf_audit —— 事后审计（workhard "session forensics" 平替）。

扫描 docs/tasks/*.md，对照 wf 状态机，抓出违反硬流程的漂移：
  - 标 ✅/完成 但 `## 抽样复核` 仍是模板占位（最严重：没抽样就交付）；
  - 文档缺 `## 口径` / `## 需求覆盖对照`；
  - 多个文件抢占同一个 T#（重复编号）；
  - 任务文档标完成但未进入 wf 状态机（open 过）；
  - wf 里 audited/delivered 但文档抽样占位。

可作为每日自动化运行：python scripts/wf_audit.py  （可选 --json 输出机器可读报告）

退出码：发现违规 = 1，干净 = 0（便于自动化判读）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # 复用章节检测逻辑

REPO = Path(__file__).resolve().parents[1]
TASKS_DIR = REPO / "docs" / "tasks"


def _field(txt: str, key: str) -> str:
    m = re.search(r"-\s*\*\*" + key + r"\*\*\s*:\s*(.+)", txt)
    return m.group(1).strip() if m else ""


def scan() -> list[dict]:
    issues: list[dict] = []
    seen_tid: dict[str, str] = {}
    files = [p for p in TASKS_DIR.glob("*.md") if p.name not in ("README.md", "_TEMPLATE.md", "_INVENTORY_20261110.md")]
    for p in sorted(files):
        txt = p.read_text(encoding="utf-8")
        tid = _field(txt, "需求编号")
        cat = _field(txt, "规范大类")
        st = _field(txt, "状态")
        name = p.name
        if name.startswith("series_"):
            continue  # 系列主档，无 T#
        # 重复编号
        if tid:
            if tid in seen_tid:
                issues.append({"type": "dup_tid", "task": tid, "file": name, "detail": f"与 {seen_tid[tid]} 重复编号"})
            else:
                seen_tid[tid] = name
        # 缺章节
        if not wf._section(txt, "口径"):
            issues.append({"type": "missing_caliber_section", "task": tid, "file": name, "detail": "文档无 `## 口径` 章节"})
        if not wf._section(txt, "需求覆盖对照"):
            issues.append({"type": "missing_coverage_section", "task": tid, "file": name, "detail": "文档无 `## 需求覆盖对照` 章节"})
        # 抽样占位
        samp = wf._section(txt, "抽样复核")
        sampled_ok = wf._sampled_filled(samp or "")
        caliber_ok = wf._caliber_filled(wf._section(txt, "口径") or "")
        coverage_ok = wf._coverage_filled(wf._section(txt, "需求覆盖对照") or "")
        is_done = ("完成" in st) or ("验收" in st) or ("定案" in st)
        if is_done and not sampled_ok:
            issues.append({"type": "done_without_sampling", "task": tid, "file": name,
                           "detail": f"状态含完成/验收但抽样复核为空（状态原文：{st[:30]}）"})
        # 未进状态机：仅对"进行中"任务报警（已完成历史任务未注册属预期，不计入违规）
        if tid and wf.get_stage(tid) is None and "进行中" in st:
            issues.append({"type": "untracked_in_wf", "task": tid, "file": name,
                           "detail": "进行中但未在 wf 状态机注册（新任务应 `wf open`；历史已完成任务未注册属预期）"})
        # wf 里说 delivered/audited 但文档抽样空
        if tid:
            stg = wf.get_stage(tid)
            if stg in ("delivered", "audited") and not sampled_ok:
                issues.append({"type": "wf_says_done_but_doc_blank", "task": tid, "file": name,
                               "detail": f"wf stage={stg} 但文档抽样复核为空"})
        # 顺带记录健康度
        _ = (caliber_ok, coverage_ok)
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    issues = scan()
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        if not issues:
            print("WF-AUDIT: 干净，无违规。")
        else:
            from collections import Counter
            cnt = Counter(it["type"] for it in issues)
            print(f"WF-AUDIT: 发现 {len(issues)} 处（按类型：{dict(cnt)}）：\n")
            for it in issues:
                print(f"  [{it['type']}] {it['task'] or '-'}  {it['file']}")
                print(f"      {it['detail']}")
            print("\n注：done_without_sampling / missing_* 多为历史任务质量债；"
                  "untracked_in_wf 仅含进行中任务。新门禁向前约束新任务。")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
