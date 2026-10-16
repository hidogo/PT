#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自选股一键同步：客户端「我的自选」(IndividualData.xml) -> 上传暂存 selfwatch.csv。

链路：
  1) 客户端自选 -> 生成 selfwatch.csv（上传暂存 data/ptrade_bridge/ + 本地 data/）
  2) 用户把 data/ptrade_bridge 定时上传到云端研究根（selfwatch.csv 落到 /home/fly/notebook/）
  3) 托管策略 _load_selfwatch 每 N bar 读 selfwatch.csv -> 实时并入统一股池，日志打 [pool] selfwatch=N

用法:
  盘前/收盘：python research/expectation/sync_selfwatch.py --sync
  上传后校验云端是否同步：python research/expectation/sync_selfwatch.py --verify-log <当日日志.txt>
  （--verify-log 用 log_collector 读 [pool] selfwatch=N，与客户端自选数比对一致/不一致）
"""
from __future__ import annotations
import argparse, datetime, os, re, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

import read_selfwatch as rsw      # noqa: E402
import log_collector as lc        # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(_HERE))          # D:/PROJ/PT
DATA = os.path.join(_ROOT, "data")
STAGING_DIR = os.path.join(DATA, "ptrade_bridge")        # 上传暂存目录
STAGING_CSV = os.path.join(STAGING_DIR, "selfwatch.csv")
LOCAL_CSV = os.path.join(DATA, "selfwatch.csv")

HEADER = "# 自选股（客户端 IndividualData.xml 自动生成；上传研究根 selfwatch.csv 供策略同步）\n"


def _write(codes, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(HEADER)
        for c in codes:
            fh.write(c + "\n")


def sync(verbose: bool = True) -> list:
    xml = rsw.DEFAULT_XML
    if not os.path.exists(xml):
        if verbose:
            print("[sync] 客户端自选文件不存在: %s" % xml)
        return []
    codes = rsw.parse(xml)          # 规范 .XSHG/.XSHE，跳过指数/板块
    os.makedirs(STAGING_DIR, exist_ok=True)
    _write(codes, STAGING_CSV)
    _write(codes, LOCAL_CSV)
    if verbose:
        print("[sync] %s -> 客户端自选 %d 只" % (STAGING_CSV, len(codes)))
        print("[sync] 本地副本: %s" % LOCAL_CSV)
        if not codes:
            print("[sync] 警告：客户端自选无 A 股（可能只有指数/板块），请在客户端添加后再跑")
        else:
            print("[sync] 把这%d只随 data/ptrade_bridge 定时上传到云端研究根（selfwatch.csv 落在 /home/fly/notebook/）" % len(codes))
    return codes


def _cloud_n(log_txt: str):
    parsed = lc.parse_text(log_txt)
    vals = []
    for e in parsed["entries"]:
        if e["type"] == "pool":
            m = re.search(r"selfwatch=(\d+)", e["body"])
            if m:
                vals.append(int(m.group(1)))
    return (vals[-1] if vals else None)


def verify(log_txt_path: str) -> int:
    if not os.path.exists(log_txt_path):
        print("[verify] 日志不存在: %s" % log_txt_path)
        return 2
    with open(log_txt_path, "r", encoding="utf-8-sig") as fh:
        txt = fh.read()
    n = len(sync(verbose=False))
    c = _cloud_n(txt)
    if c is None:
        print("[verify] 日志中未发现 [pool] selfwatch=N（大概率自选股文件尚未上传/策略未同步）")
        return 2
    if c == n:
        print("[verify] 一致：客户端自选 %d == 云端上报 selfwatch=%d" % (n, c))
        return 0
    print("[verify] 不一致：客户端自选 %d vs 云端 selfwatch=%d（未上传/未同步/文件未生效）" % (n, c))
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="sync_selfwatch")
    ap.add_argument("--sync", action="store_true", default=True, help="从客户端生成 selfwatch.csv 到上传暂存（默认执行）")
    ap.add_argument("--verify-log", default="", help="用当日交易日志(粘贴txt)校验云端 [pool] selfwatch=N 与客户端自选是否一致")
    a = ap.parse_args()
    if a.verify_log:
        return verify(a.verify_log)
    sync()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())