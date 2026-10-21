#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出板块映射（AXquant ths_board_mapping.json，同花顺行业/概念）为云端可读 CSV（v0.36d Step1）。

数据契约（列）：
  board_name,board_type,member_code

文件落到与预期 CSV 同一「待上传文件夹」PTRADE_BRIDGE_DIR（客户端定时上传会带上）：
  boards_latest.csv   稳定指针（云端读最新一版, 与 zt_lianban_latest 同约定）

用途：先只验证「生成 -> 上传 -> 云端 [boards] loaded」链路；消费逻辑（新最强板块
归属/成员切文件口径）后续再切。

注意：板块映射为低频改动文件，**不参与每日收盘/盘前一键**；仅在板块成分变化时手动
重跑一次。内容未变时跳过覆盖（UNCHANGED），避免无谓的每日覆盖/上传churn。

用法：
  python export_boards.py [--mapping <ths_board_mapping.json>] [--out-dir <上传文件夹>]
                          [--types "concept"] [--rank-limit 5]
"""
from __future__ import annotations
import argparse, csv, io, json, os

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", default=_default_mapping_path())
    ap.add_argument("--out-dir", default=bridge.PTRADE_BRIDGE_DIR)
    ap.add_argument("--types", default="concept", help="board_type 白名单（空格分隔；v0.36e 默认仅概念）")
    ap.add_argument("--rank-limit", type=int, default=5, help="每股只取前 N 个板块（v0.36e 默认5：控制并集规模）")
    args = ap.parse_args()

    with open(args.mapping, "rt", encoding="utf-8") as f:
        mapping = json.load(f)
    types = {t.strip() for t in args.types.split() if t.strip()}
    rows = build_rows(mapping, types, args.rank_limit)

    out = os.path.join(args.out_dir, "boards_latest.csv")
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
            return
    os.makedirs(args.out_dir, exist_ok=True)
    with open(out, "wt", encoding="utf-8", newline="") as f:
        f.write(content)
    boards = len({r[0] for r in rows})
    stocks = len({r[2] for r in rows})
    print("WROTE %s rows=%d boards=%d stocks=%d bytes=%d" % (
        out, len(rows), boards, stocks, os.path.getsize(out)))


if __name__ == "__main__":
    main()
