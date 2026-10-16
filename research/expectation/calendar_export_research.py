# -*- coding: utf-8 -*-
"""研究环境一次性导出权威 A 股交易日 -> data/tmp/calendar.json（bridge.calendar 消费）。

用法：
  1. 在 Ptrade「研究」模块打开本文件，把 main() 里的范围改好，粘贴/运行。
  2. 运行后 Output 显示落盘路径与导出天数。
  3. 把研究目录 data/tmp/calendar.json 下载回本地 D:/PROJ/PT/data/tmp/calendar.json
     （本地 bridge.calendar 默认从此读）。

数据源：get_trade_days(start, end)（研究/回测/交易可用，盈利含节假日与调休的准确交易日）。
没有 os 也兼容：只用内建 open；目录尽量预先创建，若不可用则只写根目录 calendar.json。
"""
import json
import os  # 研究环境可用；若被禁则不调用 makedirs

START = "2025-01-01"
END = "2026-12-31"


def _main():
    days = get_trade_days(START, END) or []
    items = []
    for d in days:
        s = str(d)
        if len(s) == 8 and s.isdigit():
            s = s[:4] + "-" + s[4:6] + "-" + s[6:8]
        items.append({"date": s})
    payload = {
        "start": START,
        "end": END,
        "count": len(items),
        "data": {"item": items},
    }
    # 优先写研究目录相对 data/tmp/calendar.json
    out = None
    try:
        base = get_research_path()
    except Exception:
        base = None
    candidates = []
    if base:
        candidates.append(os.path.join(str(base), "data", "tmp", "calendar.json"))
    candidates.append("data/tmp/calendar.json")
    candidates.append("calendar.json")
    for cand in candidates:
        try:
            d = os.path.dirname(cand)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(cand, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            out = cand
            break
        except Exception as exc:
            print("write fail", cand, exc)
    print("exports trade_days=%d -> %s" % (len(items), out))
    return len(items)


_main()