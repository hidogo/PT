#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出板块映射（AXquant ths_board_mapping.json，同花顺行业/概念）为云端可读 CSV（v0.36d Step1）。

数据契约（列）：
  board_name,board_type,member_code

文件落到与预期 CSV 同一「待上传文件夹」PTRADE_BRIDGE_DIR（客户端定时上传会带上）：
  boards_latest.csv   稳定指针（云端读最新一版, 与 zt_lianban_latest 同约定）

用途：先只验证「生成 -> 上传 -> 云端 [boards] loaded」链路；消费逻辑（新最强板块
归属/成员切文件口径）后续再切。

注意：板块映射为低频改动文件，**不参与每日收盘/盘前一键**；盘前一键仅周一固定
检查刷新（见 boards_refresh_due），内容未变时跳过覆盖（UNCHANGED），避免无谓的每日
覆盖/上传churn；距上次生成 >=14 天兜底强制刷新（防周一休市/任务失更长期不刷）。

用法：
  python export_boards.py [--mapping <ths_board_mapping.json>] [--out-dir <上传文件夹>]
                          [--types "concept"] [--rank-limit 5]
"""
from __future__ import annotations
import argparse, csv, datetime, io, json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
import bridge  # noqa: E402  # 复用 PTRADE_BRIDGE_DIR 常量


def _default_mapping_path() -> str:
    # PT research/expectation -> 项目根(D:/PROJ/PT) -> 上一级(D:/PROJ) 下的 AXquant/data
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "ths_board_mapping.json"))


def _code_ptrade(thscode: str) -> str:
    # AXquant .SH/.SZ/.BJ -> Ptrade .XSHG/.XSHE/.XBJ（与 expectation 桥接同映射）
    s = str(thscode or "").strip().split(".")[0]
    low = str(thscode or "").lower()
    if ".sz" in low:
        return s + ".XSHE"
    if ".bj" in low:
        return s + ".XBJ"
    return s + ".XSHG"


def build_rows(mapping: list, types: set, rank_limit: int) -> list:
    # 每行 (board_name, board_type, member_code)；按原文件序（股票序）输出
    rows = []
    for r in mapping or []:
        nm = str(r.get("board_name") or "").strip()
        typ = str(r.get("board_type") or "").strip()
        code = str(r.get("code") or "").strip()
        rk = int(r.get("board_rank") or 0)
        if not nm or not code or not typ:
            continue
        if types and typ not in types:
            continue
        if rank_limit and rk > rank_limit:
            continue
        rows.append((nm, typ, _code_ptrade(code)))
    return rows


def run(mapping_path: str = None, out_dir: str = None, types: str = "concept",
         rank_limit: int = 5) -> dict:
    """生成/刷新 boards_latest.csv（低频幂等：内容未变 UNCHANGED 不覆盖）。

    返回 {'status': 'WROTE'|'UNCHANGED', 'rows': n, 'boards': n, 'stocks': n}。
    盘前一键周一周更（v0.72c）与手动 CLI 共用本入口。
    """
    mapping_path = mapping_path or _default_mapping_path()
    out_dir = out_dir or bridge.PTRADE_BRIDGE_DIR
    with open(mapping_path, "rt", encoding="utf-8") as f:
        mapping = json.load(f)
    types_set = {t.strip() for t in types.split() if t.strip()}
    rows = build_rows(mapping, types_set, rank_limit)

    out = os.path.join(out_dir, "boards_latest.csv")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["board_name", "board_type", "member_code"])
    w.writerows(rows)
    content = buf.getvalue()
    # 低频文件：内容未变不覆盖（保持 mtime 稳定，避免每日无谓重传）
    if os.path.exists(out):
        with open(out, "rt", encoding="utf-8") as f:
            old = f.read()
        if old == content:
            print("UNCHANGED %s rows=%d boards=%d (低频文件, 内容未变跳过覆盖)" % (
                out, len(rows), len({r[0] for r in rows})))
            return {"status": "UNCHANGED", "rows": len(rows),
                    "boards": len({r[0] for r in rows}), "stocks": len({r[2] for r in rows})}
    os.makedirs(out_dir, exist_ok=True)
    with open(out, "wt", encoding="utf-8", newline="") as f:
        f.write(content)
    boards = len({r[0] for r in rows})
    stocks = len({r[2] for r in rows})
    print("WROTE %s rows=%d boards=%d stocks=%d bytes=%d" % (
        out, len(rows), boards, stocks, os.path.getsize(out)))
    return {"status": "WROTE", "rows": len(rows), "boards": boards, "stocks": stocks}


def boards_refresh_due(today: datetime.date, boards_fp: str = None) -> tuple:
    """板块周更决策（v0.72c，周一固定）：周一触发刷新；文件缺失或距上次生成>=14天
    （防周一休市/任务失更长期不刷）也触发。返回 (due, age_days)。
    """
    age = None
    if boards_fp and os.path.isfile(boards_fp):
        try:
            mtime = datetime.date.fromtimestamp(os.path.getmtime(boards_fp))
            age = float((today - mtime).days)
        except Exception:
            age = None
    due = (today.weekday() == 0) or (age is None) or (age is not None and age >= 14.0)
    return due, age


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", default=_default_mapping_path())
    ap.add_argument("--out-dir", default=bridge.PTRADE_BRIDGE_DIR)
    ap.add_argument("--types", default="concept", help="board_type 白名单（空格分隔；v0.36e 默认仅概念）")
    ap.add_argument("--rank-limit", type=int, default=5, help="每股只取前 N 个板块（v0.36e 默认5：控制并集规模）")
    args = ap.parse_args()
    run(args.mapping, args.out_dir, args.types, args.rank_limit)


if __name__ == "__main__":
    main()
