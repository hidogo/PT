# -*- coding: utf-8 -*-
"""
P4_exp_one_word 封单 L2 实时化的灵敏度离线测试
复刻策略 _exp_one_word 判定逻辑，对 seal_fail_ratio / seal_exceed_ratio / seal_bid_fail_ratio
做参数扫描，观察决策 CS/CM/CX 的翻转点与稳定性。
运行: python research/seal/sensitivity_test.py
"""
from __future__ import print_function

AW, CM, CS, CX = "AW", "CM", "CS", "CX"


def seal_state(seal, base, bids, bbase,
               fail_r=0.333, exceed_r=1.2, bid_enabled=True, bid_r=0.5):
    """复刻 strategy.py _exp_one_word（L2 实时化后）返回状态"""
    if base <= 0:
        return AW
    ratio = seal / base if base > 0 else 0.0
    bid_fail = False
    if bid_enabled and bbase > 0 and bids < bbase * bid_r:
        bid_fail = True
    if ratio <= fail_r or bid_fail:
        return CS
    if ratio >= exceed_r:
        return CX
    return CM


# ---- 样本情景：当日封单曲线（金额, 委托笔数） ----
# 每个情景: name, [(seal, bids), ...]（首格作 base）
SCEN = [
    ("strong_lock",   [(1_000_000, 40), (950_000, 38), (980_000, 39), (1_100_000, 41), (1_050_000, 40)]),
    ("seal_burst",    [(2_000_000, 60), (900_000, 40), (600_000, 30), (300_000, 18), (100_000, 8)]),
    ("gradual_decay", [(1_200_000, 40), (1_000_000, 35), (800_000, 30), (700_000, 26), (600_000, 22)]),
    ("bid_collapse",  [(1_100_000, 45), (1_050_000, 20), (1_020_000, 12), (1_000_000, 9)]),
    ("seal_boost",    [(800_000, 30), (1_100_000, 36), (1_400_000, 42), (1_600_000, 46), (1_900_000, 50)]),
]


def scan():
    print("=" * 108)
    print("情景判定（默认阈值 fail=%.3f exceed=%.2f bid_enabled=True bid_r=%.2f）"
          % (0.333, 1.2, 0.5))
    print("-" * 108)
    print("%-16s %-8s %-8s | 每 bar 状态序列" % ("情景", "base", "base_bids"))
    print("-" * 108)
    for name, pts in SCEN:
        base, bbase = pts[0]
        states = [seal_state(v[0], base, v[1], bbase) for v in pts[1:]]
        print("%-16s %-8d %-8d | %s" % (name, base, bbase, " ".join(states)))
    print("-" * 108)
    # 相对 base 的金额/笔数对比也打一版，便于看比值
    print("金额/笔数 相对 base 的比值")
    for name, pts in SCEN:
        base, bbase = pts[0]
        amt = ["%.2fx" % (v[0] / float(base)) for v in pts[1:]]
        bid = ["%.2fx" % (v[1] / float(bbase)) for v in pts[1:]]
        print("%-16s amt %-24s bid %s" % (name, " ".join(amt), " ".join(bid)))


def sensitivity():
    print()
    print("=" * 108)
    print("参数扫描：改变 fail/exceed/bid 阈值，统计各类决策次数（跨所有 bar 时点）")
    print("-" * 108)
    fail_vals = [0.2, 0.25, 0.333, 0.4, 0.5, 0.6]
    exceed_vals = [1.1, 1.2, 1.3, 1.5]
    bid_vals = [0.3, 0.4, 0.5, 0.6, 0.7]
    print("%-8s %-8s %-8s %-6s | %4s %4s %4s | 边界说明" %
          ("fail", "exceed", "bid_r", "bid_on", "CS", "CM", "CX"))
    print("-" * 108)
    # 逐一张量组合在两维上交叉，统计 flip 次数 = 决策随阈值改而改变的总次数（灵敏度度量）
    for fr in fail_vals:
        for er in exceed_vals:
            for br in bid_vals:
                base_states = []
                for name, pts in SCEN:
                    b, bb = pts[0]
                    base_states += [seal_state(v[0], b, v[1], bb) for v in pts[1:]]
                from collections import Counter
                c = Counter(base_states)
                # 切换 bid_on True/False 的差异
                off_states = []
                for name, pts in SCEN:
                    b, bb = pts[0]
                    off_states += [seal_state(v[0], b, v[1], bb, fr, er, False, br) for v in pts[1:]]
                diff_onoff = sum(1 for x, y in zip(base_states, off_states) if x != y)
                print("%-8.3g %-8.2f %-8.2f %-6s | %4d %4d %4d | bid切换差异=%d" %
                      (fr, er, br, True, c["CS"], c["CM"], c["CX"], diff_onoff))


def flip_analysis():
    print()
    print("=" * 108)
    print("翻转点分析：seal_burst（典型衰竭）各 bar 首达 CS 的判据")
    print("-" * 108)
    name, pts = SCEN[1]
    base, bbase = pts[0]
    print("base=%d bbase=%d" % (base, bbase))
    for i, (v, b) in enumerate(pts[1:], 1):
        ratio = v / float(base)
        bid_ratio = b / float(bbase)
        s_on = seal_state(v, base, b, bbase)
        s_off = seal_state(v, base, b, bbase, bid_enabled=False)
        print("bar%d seal=%8d ratio=%.2f bids=%3d bbid=%.2f | with-bid=%s no-bid=%s" %
              (i, v, ratio, b, bid_ratio, s_on, s_off))


if __name__ == "__main__":
    scan()
    sensitivity()
    flip_analysis()
