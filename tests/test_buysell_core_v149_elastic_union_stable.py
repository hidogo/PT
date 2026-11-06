# -*- coding: utf-8 -*-
"""v1.49 弹性概念并集账本：核心/动态分段、部分快照出值、快速预算档回归测试。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v149_union_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


def _logger():
    logs = []
    return SimpleNamespace(info=lambda msg: logs.append(msg), error=lambda msg: None,
                           warning=lambda msg: None), logs


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log, m._logs = _logger()
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-06"
    m._min_age = lambda: 5
    m._research_roots = lambda: []
    m._skip_log = lambda *a, **k: None
    m.g = SimpleNamespace(
        boards={},
        stock_boards={},
        board_type={},
        zt_lianban={},
        pool_static=[],
        watch=[],
        skip_log_ts={},
        csnap_led=None,
        csnap_last_diag=None,
    )
    return m


class _FakeDH:
    def __init__(self):
        self.spends = []

    def spend(self, source, n=1, prio=0):
        self.spends.append((source, prio))
        return True


def _concept_env(mod):
    mod.g.zt_lianban = {
        "Z1.XSHG": {"theme": "黄金/有色/资源", "themes": "黄金/有色/资源|光伏/风电/电力/储能"},
        "Z2.XSHG": {"theme": "黄金/有色/资源", "themes": "黄金/有色/资源"},
        "Z3.XSHG": {"theme": "光伏/风电/电力/储能", "themes": "光伏/风电/电力/储能"},
        "Z4.XSHG": {"theme": "光伏/风电/电力/储能", "themes": "光伏/风电/电力/储能"},
    }
    mod.g.pool_static = ["P1.XSHG"]
    mod.g.boards = {
        "黄金概念": ["Z1.XSHG", "Z2.XSHG", "G1.XSHG"],
        "小金属概念": ["Z1.XSHG", "Z2.XSHG", "G2.XSHG"],
        "稀土永磁": ["R1.XSHG"],
        "光伏概念": ["Z3.XSHG", "P1.XSHG", "P2.XSHG", "Z4.XSHG"],
        "半导体概念": ["D1.XSHG", "D2.XSHG"],
    }
    mod.g.stock_boards = {
        "Z1.XSHG": ["黄金概念", "小金属概念"],
        "Z2.XSHG": ["黄金概念", "小金属概念"],
        "Z3.XSHG": ["光伏概念"],
        "Z4.XSHG": ["光伏概念"],
        "P1.XSHG": ["光伏概念"],
        "G1.XSHG": ["黄金概念"],
        "G2.XSHG": ["小金属概念"],
        "R1.XSHG": ["稀土永磁"],
        "D1.XSHG": ["半导体概念"],
        "D2.XSHG": ["半导体概念"],
    }
    mod.g.board_type = {b: "concept" for b in mod.g.boards}
    mod._get_snapshot_many = lambda secs, cap: {s: {"preclose_px": 10.0, "last_px": 10.0} for s in secs}
    return mod


def test_dynamic_board_append_does_not_reset_core_ratio(mod):
    mod = _concept_env(mod)
    mod.BLS["frame_snap_batch_fast"] = 2
    dh = _FakeDH()
    mod._get_ds = lambda: dh

    _snap, ratio, diag = mod._concept_snap_union(["黄金概念", "光伏概念"], budget="board_union")
    assert diag["key_changed"] == 1
    assert diag["core_total"] == 7
    assert diag["core_ratio"] == pytest.approx(2.0 / 7.0)

    mod.g.csnap_led["ts"] = 0.0
    _snap, ratio, diag = mod._concept_snap_union(["黄金概念", "光伏概念"], budget="board_union")
    assert diag["core_ratio"] == pytest.approx(4.0 / 7.0)

    mod.g.csnap_led["ts"] = 0.0
    _snap, ratio, diag = mod._concept_snap_union(
        ["黄金概念", "光伏概念", "半导体概念"], budget="board_union")
    assert diag["added_boards"] == 1
    assert diag["dyn_total"] == 2
    assert diag["dyn_done"] == 0
    assert diag["core_ratio"] == pytest.approx(6.0 / 7.0)

    mod.g.csnap_led["ts"] = 0.0
    _snap, ratio, diag = mod._concept_snap_union(
        ["黄金概念", "光伏概念", "半导体概念"], budget="board_union")
    assert ratio == 1.0
    assert diag["core_ratio"] == 1.0
    assert diag["dyn_done"] == 0
    assert diag["complete"] is False

    mod.g.csnap_led["ts"] = 0.0
    _snap, ratio, diag = mod._concept_snap_union(
        ["黄金概念", "光伏概念", "半导体概念"], budget="board_union")
    assert ratio == 1.0
    assert diag["dyn_done"] == 2
    assert diag["complete"] is True


def test_partial_snapshot_still_emits_top1(mod):
    mod = _concept_env(mod)
    mod._concept_snap_union = lambda boards, budget=None, prio=0, force=False: (
        {"Z1.XSHG": {"preclose_px": 10.0, "last_px": 10.5}},
        0.3,
        {"ratio": 0.3, "core_total": 7, "dyn_total": 2, "dyn_done": 0},
    )
    mod._board_family_of = lambda b: {
        "黄金概念": "黄金/有色/资源",
        "小金属概念": "黄金/有色/资源",
        "光伏概念": "光伏",
    }.get(b, b)
    mod._concept_board_strength = lambda b, snap=None: {
        "黄金概念": 3.0,
        "小金属概念": 2.9,
        "光伏概念": 2.5,
    }.get(b, 0.0)
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)

    top, lead = mod._compute_concept_board_top1_lead(["黄金概念", "小金属概念", "光伏概念"])
    assert top == "黄金概念"
    assert lead == pytest.approx(0.5)
    assert mod.g.csnap_last_diag["reason"] == "partial"
    assert any("[csnap-partial]" in x for x in logs)


def test_no_snapshot_returns_coverage_reason(mod):
    mod = _concept_env(mod)
    mod._concept_snap_union = lambda boards, budget=None, prio=0, force=False: (
        {}, 0.2, {"ratio": 0.2, "core_total": 7, "dyn_total": 2, "dyn_done": 0},
    )
    mod._board_family_of = lambda b: b
    mod._concept_board_strength = lambda b, snap=None: 1.0

    top, lead = mod._compute_concept_board_top1_lead(["黄金概念"])
    assert top is None
    assert mod.g.csnap_last_diag["reason"] == "coverage"


def test_csnap_batch_cap_fast_and_normal(mod):
    mod = _concept_env(mod)
    mod.BLS["frame_snap_batch_fast"] = 250
    mod.BLS["frame_snap_batch"] = 100
    assert mod._csnap_batch_cap() == 250

    mod._min_age = lambda: 60
    mod._hhmm = lambda: "10:15"
    assert mod._csnap_batch_cap() == 100


def test_source_limit_board_union_fast_and_normal(mod):
    mod._min_age = lambda: 5
    assert mod._source_limit("board_union") == float(mod.BLS["frame_board_union_limit_fast"])

    mod._min_age = lambda: 60
    mod._hhmm = lambda: "10:15"
    assert mod._source_limit("board_union") == float(mod.BLS["frame_board_union_limit"])
