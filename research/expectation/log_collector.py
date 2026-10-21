#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集器：把交易模块粘贴的日志解析成结构化 JSON，供封单/持仓/L2 阈值回归与复盘对账。

数据源：Ptrade 托管策略沙盒日志（仅在交易 UI 可见，需人工粘贴/另存为 .txt 传入）。
客户端 PTradeQuantApi 无策略日志接口（docs/22），故采用"贴文本 -> 解析入库"模式。

用法（本地 Python 均可，纯 stdlib）:
  python research/expectation/log_collector.py ingest --file <当日日志.txt> --date 2026-10-16
  python research/expectation/log_collector.py summary --date 2026-10-16

产出:
  data/logs/log_<date>.json       结构化日志（l2/seal/may_order/score/expect/errors）
  data/logs/log_<date>.seal.csv   [seal] 行汇总（供 threshold 回归）
  data/logs/log_<date>.signal.csv [signal] 行汇总（买卖信号->回报对账）
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # D:/PROJ/PT
LOGS_DIR = os.path.join(_ROOT, "data", "logs")

_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (INFO|ERROR|WARN|DEBUG) - (.*)$")


def _split_lines(text):
    # 兼容 PTrade 粘贴的折行转义（行尾 \ 续行 / \n / &#x20; 空格转义）
    t = text.replace("&#x20;", " ")
    t = t.replace("\\n", "\n").replace("\\r", "")
    lines = []
    for raw in t.split("\n"):
        raw = raw.replace("\\ ", " ").replace("\\", "\\")  # 去掉续行反斜杠
        if raw.strip():
            lines.append(raw)
    return lines


def _classify(body):
    b = body.strip()
    if b.startswith("[l2] "):
        return "l2"
    if b.startswith("[pool] "):
        return "pool"
    if b.startswith("[firstzt] "):
        return "firstzt"
    if b.startswith("[seal] "):
        return "seal"
    if b.startswith("[signal] "):
        return "signal"
    if b.startswith("[may-order] "):
        return "may_order"
    if b.startswith("[exp-order] ") or b.startswith("[exp] "):
        return "exp_order"
    if b.startswith("score "):
        return "score"
    if b.startswith("market_scan "):
        return "market_scan"
    if b.startswith("expectation ") or b.startswith("expect "):
        return "expect"
    if b.startswith("buysell_core "):
        return "init"
    if ("Exception" in b) or b.startswith("Traceback") or b.startswith("入参错误") or ("missing " in b):
        return "error"
    return "other"


def parse_text(text):
    entries = []
    for ln in _split_lines(text):
        m = _PREFIX.match(ln.strip())
        if not m:
            if entries and ln.strip():
                entries[-1]["body"] += " " + ln.strip()
            continue
        ts, lvl, body = m.group(1), m.group(2), m.group(3)
        entries.append({"time": ts, "level": lvl, "type": _classify(body), "body": body.strip()})
    return {"entries": entries}


def _agg(entries):
    dates = {}
    keys = ["l2", "pool", "firstzt", "seal", "signal", "may_order", "exp_order", "score", "market_scan", "expect", "error", "init"]
    for e in entries:
        d = e["time"][:10]
        if d not in dates:
            dates[d] = {k: [] for k in keys}
        tp = e["type"]
        if tp in dates[d]:
            dates[d][tp].append({"time": e["time"], "level": e["level"], "body": e["body"]})
    return dates


def ingest(file, date):
    with open(file, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    day = date or datetime.date.today().isoformat()
    os.makedirs(LOGS_DIR, exist_ok=True)
    parsed = parse_text(text)
    agg = _agg(parsed["entries"])
    out = {"date": day, "source": os.path.abspath(file), "count": len(parsed["entries"]), "by_day": agg}
    fp = os.path.join(LOGS_DIR, "log_%s.json" % day)
    with open(fp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    seals = agg.get(day, {}).get("seal", [])
    if seals:
        cfp = os.path.join(LOGS_DIR, "log_%s.seal.csv" % day)
        with open(cfp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "sec", "seal", "base", "ratio", "bids", "bid_fail", "state"])
            for s in seals:
                w.writerow([s["time"]] + _parse_seal(s["body"]))
    sigs = agg.get(day, {}).get("signal", [])
    if sigs:
        sfp = os.path.join(LOGS_DIR, "log_%s.signal.csv" % day)
        with open(sfp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "sec", "side", "qty", "limit", "mode", "note", "score", "ent", "status"])
            for s in sigs:
                w.writerow([s["time"]] + _parse_signal(s["body"]))
    return fp


def _parse_seal(body):
    m = re.search(r"(\S+\.(?:XSHG|XSHE|XBJ))", body)
    code = m.group(1) if m else ""

    def f(key):
        mm = re.search(key + r"=([-\d.]+)", body)
        return mm.group(1) if mm else ""

    state = ""
    if " -> " in body:
        state = body.split("->")[-1].strip().split()[0]
    return [code, f("seal"), f("base"), f("ratio"), f("bids"), f("bid_fail"), state]


def _parse_signal(body):
    m = re.search(r"(\S+\.(?:XSHG|XSHE|XBJ))", body)
    code = m.group(1) if m else ""
    def gs(key):
        mm = re.search(key + r"=([^ ]+)", body)
        return mm.group(1) if mm else ""
    return [code, gs("side"), gs("qty"), gs("limit"), gs("mode"), gs("note"), gs("score"), gs("ent"), gs("status")]


def summary(date):
    day = date or datetime.date.today().isoformat()
    fp = os.path.join(LOGS_DIR, "log_%s.json" % day)
    if not os.path.exists(fp):
        print("no log for %s: %s" % (day, fp))
        return 1
    with open(fp, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    print("== log summary %s (source=%s, lines=%d) ==" % (day, data.get("source"), data.get("count")))
    d = data.get("by_day", {}).get(day, {})
    l2 = d.get("l2", [])
    print("L2 探针(%d):" % len(l2))
    for e in l2:
        print("   %s %s" % (e["time"], e["body"]))
    pools = d.get("pool", [])
    print("股池 [pool](%d):" % len(pools))
    for e in pools:
        print("   %s %s" % (e["time"], e["body"]))
    fzt = d.get("firstzt", [])
    print("首笔涨停 [firstzt](%d):" % len(fzt))
    for e in fzt:
        print("   %s %s" % (e["time"], e["body"]))
    seals = d.get("seal", [])
    print("封单 [seal](%d):" % len(seals))
    for e in seals:
        print("   %s %s" % (e["time"], e["body"]))
    mo = d.get("may_order", [])
    print("may-order(%d):" % len(mo))
    for e in mo:
        print("   %s %s" % (e["time"], e["body"]))
    expo = d.get("exp_order", [])
    print("exp-order/exp(%d):" % len(expo))
    for e in expo:
        print("   %s %s" % (e["time"], e["body"]))
    err = list(d.get("error", []))
    print("errors/异常(%d):" % len(err))
    for e in err[:20]:
        print("   %s %s" % (e["time"], e["body"][:160]))
    return 0


def main():
    p = argparse.ArgumentParser(prog="log_collector")
    sub = p.add_subparsers(dest="cmd", required=True)
    si = sub.add_parser("ingest", help="解析粘贴的当日日志")
    si.add_argument("--file", required=True)
    si.add_argument("--date", default="")
    ss = sub.add_parser("summary", help="打印某日采集摘要")
    ss.add_argument("--date", default="")
    a = p.parse_args()
    if a.cmd == "ingest":
        fp = ingest(a.file, a.date)
        print("ingested -> %s" % fp)
        return summary(a.date)
    if a.cmd == "summary":
        return summary(a.date)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())