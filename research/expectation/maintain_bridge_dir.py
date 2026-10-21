#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""待上传目录瘦身/归档：控制 ptrade_bridge 根目录文件数与体积（定时上传有数据限制）。

背景：定时上传任务按文件夹上传（观察为**非递归**：archive/ 子目录不上传）。
每交易日收盘/盘前会生成 预期/涨停/情绪 三类 dated 文件（<prefix>_YYYY-MM-DD.csv）
+ *_latest.csv 稳定指针；dated 逐日累积 -> 上传文件数/体积持续增长，触发上传数据限制。

策略（上传载荷恒定）：
  - 根目录只保留 *_latest 稳定指针（dated 一律移入 archive/，keep-dated 默认 0）——定时上传文件数恒定，云端消费 latest 优先；
  - 更早的 dated 移入 archive/（定时上传非递归 -> 从上传载荷移除，本地仍可追溯/重传）；
  - archive/ 内 dated 按文件名日期超过保留天数（默认 30 天）删除，防本地磁盘无界增长；
  - 永不触碰 *_latest.csv / selfwatch.csv / boards_latest.csv 及非 dated 文件（含 archive/ 内其它产物）。

用法（本机 Python3.10）：
  python maintain_bridge_dir.py [--root <待上传根>] [--keep-dated 0] [--archive-days 30] [--dry-run]

挂接：run_one_click_after_close（步骤6）/ run_one_click_premarket（步骤3b），默认参数即可。
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402

DATED_RE = re.compile(r"^(expectation|zt_lianban|sentiment)_(\d{4}-\d{2}-\d{2})\.csv$")


def _dated_entries(root: str) -> list:
    """root 内 dated 文件列表：[(family, date, name, size)]，按 (family, date) 排序。"""
    out = []
    try:
        names = os.listdir(root)
    except OSError:
        return out
    for n in names:
        m = DATED_RE.match(n)
        if not m:
            continue
        fp = os.path.join(root, n)
        try:
            d = datetime.date.fromisoformat(m.group(2))
            size = os.path.getsize(fp)
        except (ValueError, OSError):
            continue
        out.append((m.group(1), d, n, size))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="maintain_bridge_dir",
                                 description="待上传目录瘦身：根目录只留 *_latest， dated 全移 archive/；archive 超期清理")
    ap.add_argument("--root", default="", help="待上传根目录（默认 PTRADE_BRIDGE_DIR）")
    ap.add_argument("--keep-dated", type=int, default=0, help="根目录每类 dated 保留最新 N 个(0=只留 *_latest)")
    ap.add_argument("--archive-days", type=int, default=30, help="archive 内 dated 按文件名日期保留天数")
    ap.add_argument("--dry-run", action="store_true", help="仅预览：显示将移动/删除的文件，不执行")
    a = ap.parse_args(argv)

    root = os.path.abspath(a.root or bridge.PTRADE_BRIDGE_DIR)
    if not os.path.isdir(root):
        print("[maintain] root 不存在: %s" % root)
        return 0
    arch = os.path.join(root, "archive")
    keep = max(int(a.keep_dated), 0)   # 0 = 只留 *_latest，dated 全移 archive（上传数量限制）
    arch_days = max(int(a.archive_days), 1)

    before_files, before_bytes = 0, 0
    try:
        for _n in os.listdir(root):
            _fp = os.path.join(root, _n)
            if os.path.isfile(_fp):
                before_files += 1
                before_bytes += os.path.getsize(_fp)
    except OSError:
        pass

    moves, deletes = [], []
    # 1) 根目录 dated 每类只留最新 keep 个
    by_fam = {}
    for fam, d, n, size in _dated_entries(root):
        by_fam.setdefault(fam, []).append((d, n))
    for fam, entries in sorted(by_fam.items()):
        entries.sort(reverse=True)  # 日期新的在前
        for d, n in entries[keep:]:
            moves.append((os.path.join(root, n), os.path.join(arch, n), fam, d))

    # 2) archive/ 内 dated 超期清理
    today = datetime.date.today()
    for fam, d, n, size in _dated_entries(arch):
        if (today - d).days > arch_days:
            deletes.append(os.path.join(arch, n))

    # 报告
    if moves:
        print("[maintain] 根目录 dated 超保留(keep=%d) 将移入 archive/: %d 个" % (keep, len(moves)))
        for src, dst, fam, d in sorted(moves, key=lambda t: t[2]):
            print("  [move] %s/%s (%s)" % (fam, d.isoformat(), os.path.basename(src)))
    if deletes:
        print("[maintain] archive/ dated 超 %d 天将删除: %d 个" % (arch_days, len(deletes)))
        for fp in sorted(deletes):
            print("  [del] %s" % os.path.basename(fp))
    if not moves and not deletes:
        print("[maintain] 无需清理（根目录无 dated，archive 无超期）" if keep == 0 else "[maintain] 无需清理（根目录每类 dated <= %d，archive 无超期）" % keep)

    if not a.dry_run:
        os.makedirs(arch, exist_ok=True)
        for src, dst, _fam, _d in moves:
            try:
                shutil.move(src, dst)
            except OSError as e:
                print("[maintain] 移动 %s 失败: %r" % (os.path.basename(src), e))
        for fp in deletes:
            try:
                os.remove(fp)
            except OSError as e:
                print("[maintain] 删除 %s 失败: %r" % (os.path.basename(fp), e))

    after_files, after_bytes = 0, 0
    try:
        for _n in os.listdir(root):
            _fp = os.path.join(root, _n)
            if os.path.isfile(_fp):
                after_files += 1
                after_bytes += os.path.getsize(_fp)
    except OSError:
        pass
    print("[maintain] %s: 根目录文件 %d -> %d 个, 体积 %d -> %d B (%d 个移入 archive/, %d 个删除)"
          % ("dry-run 预览" if a.dry_run else "完成", before_files, after_files, before_bytes, after_bytes,
             len(moves), len(deletes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
