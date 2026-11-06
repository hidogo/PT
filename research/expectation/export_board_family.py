#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出家族映射（人工 override + 全量概念成员 + 近 10 日题材桶）为云端可读 CSV（v1.42）。

数据契约（列）：
  board_name,family_name

文件落到与预期 CSV 同一「待上传文件夹」PTRADE_BRIDGE_DIR（客户端定时上传会带上）：
  board_family_latest.csv   稳定指针（云端读最新一版, 与 boards_latest 同约定）

用途：把代码内的 board_family_override 映射块移到云端文件；策略 _load_board_family
读该文件作为人工覆盖层，自动映射（T-1 题材桶）仍为兜底。

生成优先级（v1.42，用户确认后实施）：
  1) 人工 override（AXquant/data/board_family_override.json，最高优先级）；
  2) 未人工覆盖的概念板按成员重叠自动归族：ths_board_mapping.json 全量 concept 成员
     + 近 10 交易日 review_analysis_*.json 题材桶；最新日桶优先，历史同名桶累积兜底；
  3) min_overlap 默认 2（重叠>=2 才归属，覆盖约 82.6% 且误并风险低）；
  4) 无重叠的板不输出（策略侧自动映射兜底仍可消费）。

刷新节奏：收盘一键每日导出 + 盘前每日检查（内容未变 UNCHANGED 不覆盖），
不再复用 boards_refresh_due 周一/14 天低频节奏；boards_latest.csv 保持低频不合并。

鲁棒性：人工 override 缺失/损坏/为空时保留既有文件（人工覆盖不静默丢失）；
ths_board_mapping.json 缺失/损坏时同样保留既有文件；题材桶缺失时仅人工+空自动，不失败。

用法：
  python export_board_family.py [--mapping <board_family_override.json>]
                                [--ths-mapping <ths_board_mapping.json>]
                                [--analysis-dir <review_analysis 目录>]
                                [--min-overlap 2] [--out-dir <上传文件夹>]
"""
from __future__ import annotations
import argparse, csv, io, json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
import bridge  # noqa: E402  # 复用 PTRADE_BRIDGE_DIR 常量


def _default_mapping_path() -> str:
    # PT research/expectation -> 项目根(D:/PROJ/PT) -> 上一级(D:/PROJ) 下的 AXquant/data
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "board_family_override.json"))


def _default_ths_mapping_path() -> str:
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "ths_board_mapping.json"))


def _default_analysis_dir() -> str:
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "tmp"))


def _norm_code(code: str) -> str:
    # AXquant(.SH/.SZ/.BJ) 与 PTrade(.XSHG/.XSHE/.XBJ) 双口径归一，防重叠误算为 0
    s = str(code or "").strip().upper()
    if s.endswith(".XSHG"):
        return s[:-5] + ".SH"
    if s.endswith(".XSHE"):
        return s[:-5] + ".SZ"
    if s.endswith(".XBJ"):
        return s[:-5] + ".BJ"
    return s


def _analysis_files(analysis_dir: str, limit: int = 10) -> list:
    # review_analysis_YYYY-MM-DD.json，按日期名升序取最近 limit 个
    if not analysis_dir or not os.path.isdir(analysis_dir):
        return []
    names = [n for n in os.listdir(analysis_dir)
             if n.startswith("review_analysis_") and n.endswith(".json")]
    names.sort()
    return [os.path.join(analysis_dir, n) for n in names[-limit:]]


def _load_buckets_by_date(paths: list) -> list:
    """返回 [(date, {bucket_name: set(codes)}), ...]，最新日期在前。"""
    out = []
    for p in paths:
        date = os.path.basename(p).replace("review_analysis_", "").replace(".json", "")
        try:
            with open(p, "rt", encoding="utf-8") as f:
                data = json.load(f)
            buckets = (data or {}).get("theme", {}).get("buckets") or {}
        except Exception as e:
            print("  [family] 题材桶读取失败跳过 %s (%r)" % (p, e))
            continue
        norm = {}
        for name, b in (buckets or {}).items():
            codes = {_norm_code(c) for c in (b.get("codes") or [])}
            codes.discard("")
            nm = str(name or "").strip()
            if nm and codes:
                norm[nm] = codes
        if norm:
            out.append((date, norm))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def _concept_members(mapping: list) -> dict:
    # 全量概念板成员：board_name -> set(codes)，与 export_boards 同源但不截断 rank
    out = {}
    for r in mapping or []:
        if str(r.get("board_type") or "").strip() != "concept":
            continue
        nm = str(r.get("board_name") or "").strip()
        code = _norm_code(r.get("code"))
        if nm and code:
            out.setdefault(nm, set()).add(code)
    return out


def _best_bucket(members: set, buckets: dict, min_overlap: int):
    # 取重叠家数最大的桶；同重叠取字典序小的桶名保证确定性
    best_name = None
    best_ov = -1
    for name, codes in buckets.items():
        ov = len(members & codes)
        if ov < min_overlap:
            continue
        if ov > best_ov or (ov == best_ov and (best_name is None or name < best_name)):
            best_ov = ov
            best_name = name
    return best_name, best_ov


def _auto_family_map(concept_members: dict, buckets_by_date: list, min_overlap: int):
    """最新日桶优先，历史（近 10 日同名桶并集）累积兜底。返回 (family_map, overlap_dist)。"""
    latest = buckets_by_date[0][1] if buckets_by_date else {}
    hist = {}
    for _date, buckets in buckets_by_date[1:]:
        for name, codes in buckets.items():
            hist.setdefault(name, set()).update(codes)
    out = {}
    dist = {}
    for board, members in concept_members.items():
        best_name, best_ov = _best_bucket(members, latest, min_overlap)
        if best_name is None:
            best_name, best_ov = _best_bucket(members, hist, min_overlap)
        if best_name is not None:
            out[board] = best_name
            dist[best_ov] = dist.get(best_ov, 0) + 1
    return out, dist


def build_rows(manual: dict, concept_members: dict = None,
               buckets_by_date: list = None, min_overlap: int = 2) -> list:
    # 每行 (board_name, family_name)；人工优先，自动补充；按 board_name 排序稳定输出
    merged = {}
    for b, f in (manual or {}).items():
        b = str(b or "").strip()
        f = str(f or "").strip()
        if b and f:
            merged[b] = f
    if concept_members:
        auto, _dist = _auto_family_map(concept_members, buckets_by_date or [], min_overlap)
        for b, f in auto.items():
            if b and f and b not in merged:
                merged[b] = f
    return [(b, merged[b]) for b in sorted(merged)]


def _write_csv(out_dir: str, rows: list) -> str:
    out = os.path.join(out_dir, "board_family_latest.csv")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["board_name", "family_name"])
    w.writerows(rows)
    content = buf.getvalue()
    # 每日导出：内容未变不覆盖（保持 mtime 稳定，避免每日无谓重传）
    if os.path.exists(out):
        with open(out, "rt", encoding="utf-8") as f:
            old = f.read()
        if old == content:
            print("UNCHANGED %s rows=%d (内容未变跳过覆盖)" % (out, len(rows)))
            return "UNCHANGED"
    os.makedirs(out_dir, exist_ok=True)
    with open(out, "wt", encoding="utf-8", newline="") as f:
        f.write(content)
    print("WROTE %s rows=%d bytes=%d" % (out, len(rows), os.path.getsize(out)))
    return "WROTE"


def run(mapping_path: str = None, out_dir: str = None, ths_mapping_path: str = None,
        analysis_dir: str = None, min_overlap: int = 2) -> dict:
    """生成/刷新 board_family_latest.csv（每日幂等：内容未变 UNCHANGED 不覆盖）。

    返回 {'status': 'WROTE'|'UNCHANGED'|'MISSING_SOURCE'|'INVALID_SOURCE'|'EMPTY_SOURCE',
          'rows': n, 'boards': n, 'manual_rows': n, 'auto_boards': n, 'overlap_dist': {...}}。
    人工 override / ths 主源缺失或损坏时不覆盖既有文件，避免覆盖层静默丢失。
    """
    mapping_path = mapping_path or _default_mapping_path()
    out_dir = out_dir or bridge.PTRADE_BRIDGE_DIR
    ths_mapping_path = ths_mapping_path or _default_ths_mapping_path()
    analysis_dir = analysis_dir or _default_analysis_dir()

    if not os.path.isfile(mapping_path):
        print("MISSING_SOURCE %s -> 保留既有 board_family_latest.csv（人工覆盖不丢失）" % mapping_path)
        return {"status": "MISSING_SOURCE", "rows": 0, "boards": 0}
    try:
        with open(mapping_path, "rt", encoding="utf-8") as f:
            manual = json.load(f)
    except Exception as e:
        print("INVALID_SOURCE %s (%r) -> 保留既有 board_family_latest.csv（人工覆盖不丢失）" % (mapping_path, e))
        return {"status": "INVALID_SOURCE", "rows": 0, "boards": 0}
    if not isinstance(manual, dict) or not any(str(b).strip() and str(f).strip() for b, f in manual.items()):
        print("EMPTY_SOURCE %s -> 保留既有 board_family_latest.csv（人工覆盖不丢失）" % mapping_path)
        return {"status": "EMPTY_SOURCE", "rows": 0, "boards": 0}
    manual = {str(b).strip(): str(f).strip() for b, f in manual.items() if str(b).strip() and str(f).strip()}

    if not os.path.isfile(ths_mapping_path):
        print("MISSING_SOURCE %s -> 保留既有 board_family_latest.csv（概念主源不丢失）" % ths_mapping_path)
        return {"status": "MISSING_SOURCE", "rows": 0, "boards": 0}
    try:
        with open(ths_mapping_path, "rt", encoding="utf-8") as f:
            mapping = json.load(f)
    except Exception as e:
        print("INVALID_SOURCE %s (%r) -> 保留既有 board_family_latest.csv（概念主源不丢失）" % (ths_mapping_path, e))
        return {"status": "INVALID_SOURCE", "rows": 0, "boards": 0}
    if not isinstance(mapping, list) or not mapping:
        print("EMPTY_SOURCE %s -> 保留既有 board_family_latest.csv（概念主源不丢失）" % ths_mapping_path)
        return {"status": "EMPTY_SOURCE", "rows": 0, "boards": 0}

    paths = _analysis_files(analysis_dir)
    if not paths:
        print("  [family] 未找到题材桶(review_analysis_*.json) -> 仅人工+空自动（不失败）")
    buckets_by_date = _load_buckets_by_date(paths)
    concept_members = _concept_members(mapping)
    rows = build_rows(manual, concept_members, buckets_by_date, min_overlap)
    if not rows:
        print("EMPTY_SOURCE (人工为空且无自动映射) -> 保留既有 board_family_latest.csv")
        return {"status": "EMPTY_SOURCE", "rows": 0, "boards": 0}

    auto, dist = _auto_family_map(concept_members, buckets_by_date, min_overlap)
    status = _write_csv(out_dir, rows)
    return {
        "status": status,
        "rows": len(rows),
        "boards": len(rows),
        "manual_rows": len(manual),
        "auto_boards": len(auto),
        "overlap_dist": dist,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", default=_default_mapping_path())
    ap.add_argument("--ths-mapping", default=_default_ths_mapping_path())
    ap.add_argument("--analysis-dir", default=_default_analysis_dir())
    ap.add_argument("--min-overlap", type=int, default=2)
    ap.add_argument("--out-dir", default=bridge.PTRADE_BRIDGE_DIR)
    args = ap.parse_args()
    run(args.mapping, args.out_dir, args.ths_mapping, args.analysis_dir, args.min_overlap)


if __name__ == "__main__":
    main()
