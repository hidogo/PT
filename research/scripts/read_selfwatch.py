#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 PTrade 客户端本地的「我的自选」数据，转成 selfwatch.csv 供托管策略同步。

自选股存于客户端本机: D:\\gjzq\\ptrade\\Data\\IndividualData.xml
  <IndividualMenu Name="我的自选"><QuoteCode ProdCode="6位代码" MarketCode="市场编码"/></IndividualMenu>
  MarketCode: XSHG/XSHE/XBJ 前缀映射到 .XSHG/.XSHE/.XBJ；含 .MRI 的是指数/板块（跳过），.ESA 为个股。

策略沙盒(云端)读不到客户端本地文件：先在本机跑本脚本生成 selfwatch.csv，
再手动/定时上传到云端研究根（或 data/）即可被 strategies/buysell_core 的 _load_selfwatch 实时同步。
用法:
  python research/scripts/read_selfwatch.py
  python research/scripts/read_selfwatch.py --xml <客户端 IndividualData.xml 路径> --out <目标 selfwatch.csv>
"""
from __future__ import annotations
import argparse, os, xml.etree.ElementTree as ET

DEFAULT_XML = r"D:\gjzq\ptrade\Data\IndividualData.xml"
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "selfwatch.csv")
EXCH = {"XSHG": ".XSHG", "XSHE": ".XSHE", "XBJ": ".XBJ"}


def parse(xml_path: str, menu: str = "我的自选") -> list:
    codes = []
    tree = ET.parse(xml_path)
    for menu_el in tree.getroot().iter("IndividualMenu"):
        if (menu_el.get("Name") or "") != menu:
            continue
        for q in menu_el.iter("QuoteCode"):
            prod = (q.get("ProdCode") or "").strip()
            mk = (q.get("MarketCode") or "").strip()
            if not prod or not mk:
                continue
            if ".MRI" in mk:      # 指数/板块，跳过
                continue
            pref = mk.split(".")[0].upper()
            suf = EXCH.get(pref)
            if not suf:
                continue
            codes.append(prod + suf)
    # 去重保序
    return list(dict.fromkeys(codes))


def main() -> int:
    ap = argparse.ArgumentParser(prog="read_selfwatch")
    ap.add_argument("--xml", default=DEFAULT_XML)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--menu", default="我的自选")
    ap.add_argument("--print", dest="do_print", action="store_true", help="仅打印不写文件")
    a = ap.parse_args()
    if not os.path.exists(a.xml):
        print("客户端自选股文件不存在: %s" % a.xml, file=__import__("sys").stderr)
        return 1
    codes = parse(a.xml, a.menu)
    if not codes:
        print("「%s」下没有可用的 A 股自选（可能只有指数/板块，或菜单名不同）" % a.menu)
    if a.do_print:
        for c in codes:
            print(c)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# 自选股（由客户端 IndividualData.xml 自动生成，可再手改）\n")
        for c in codes:
            fh.write(c + "\n")
    print("已生成 %s（%d 只）" % (a.out, len(codes)))
    print("上传该文件到云端研究根 selfwatch.csv（或 data/selfwatch.csv）即可被策略实时同步。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())