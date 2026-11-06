# -*- coding: utf-8 -*-
"""v1.39 弹性 top1/top3 概念并集：题材族去重、账本 key 稳定、board_union 独立预算、覆盖率审计回归测试。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v139_union_test", STRATEGY_PATH)
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
    m.get_trading_day = lambda: "2026-11-05"
    m._min_age = lambda: 5
    m._research_roots = lambda: []
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
        self.cache = {}

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


def test_board_family_auto_map_and_override(mod, tmp_path):
    mod = _concept_env(mod)
    mod.BLS["board_family_min_overlap"] = 2
    fam = tmp_path / "board_family_latest.csv"
    fam.write_text(
        "board_name,family_name\n"
        "黄金概念,黄金/有色/资源\n"
        "小金属概念,黄金/有色/资源\n"
        "稀土永磁,黄金/有色/资源\n"
        "金属铜,黄金/有色/资源\n",
        encoding="utf-8",
    )
    mod._research_roots = lambda: [str(tmp_path) + "/"]
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"
    assert mod._board_family_of("小金属概念") == "黄金/有色/资源"
    assert mod._board_family_of("稀土永磁") == "黄金/有色/资源"
    assert mod._board_family_of("金属铜") == "黄金/有色/资源"
    assert mod._board_family_of("光伏概念") == "光伏/风电/电力/储能"
    assert mod._board_family_of("半导体概念") == "半导体概念"

    mod.g.board_family_map = None
    mod._research_roots = lambda: []
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"


def test_compute_concept_board_rank_dedupe_family(mod):
    mod._concept_snap_union = lambda boards, budget=None, prio=0, force=False: ({}, 1.0, {"ratio": 1.0})
    mod._board_family_of = lambda b: {
        "黄金概念": "黄金/有色/资源",
        "小金属概念": "黄金/有色/资源",
        "光伏概念": "光伏",
        "半导体概念": "半导体",
    }.get(b, b)
    mod._concept_board_strength = lambda b, snap=None: {
        "黄金概念": 3.0,
        "小金属概念": 2.9,
        "光伏概念": 2.5,
        "半导体概念": 2.0,
    }.get(b, 0.0)
    mod.BLS["board_rank_top_n"] = 3

    out = mod._compute_concept_board_rank(["黄金概念", "小金属概念", "光伏概念", "半导体概念"])
    assert out == {"黄金概念", "光伏概念", "半导体概念"}


def test_compute_concept_board_top1_lead_uses_family(mod):
    mod._concept_snap_union = lambda boards, budget=None, prio=0, force=False: ({}, 1.0, {"ratio": 1.0})
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

    top, lead = mod._compute_concept_board_top1_lead(["黄金概念", "小金属概念", "光伏概念"])
    assert top == "黄金概念"
    assert lead == pytest.approx(0.5)


def test_csnap_key_drift_increments_without_rebuild(mod):
    mod = _concept_env(mod)
    dh = _FakeDH()
    mod._get_ds = lambda: dh

    _snap, ratio, diag = mod._concept_snap_union(["黄金概念", "光伏概念"], budget="board_union")
    assert ratio == 1.0
    assert diag["total"] == 7
    assert diag["key_changed"] == 1

    mod.g.csnap_led["ts"] = 0.0   # 模拟下一帧：绕开 3s TTL 提前返回，验证增量补板
    _snap2, ratio2, diag2 = mod._concept_snap_union(
        ["黄金概念", "光伏概念", "半导体概念"], budget="board_union")
    assert ratio2 == 1.0
    assert diag2["key_changed"] == 0
    assert diag2["added_boards"] == 1
    assert diag2["total"] == 9
    assert len(mod.g.csnap_led["members"]) == 9
    assert mod.g.csnap_led["members"][-2:] == ["D1.XSHG", "D2.XSHG"]


def test_csnap_for_rejects_boards_not_in_led(mod):
    # v1.39 稳定 key 可能包含尚未入账的兄弟概念：只认 led.boards 已建成员的板块，
    # 未入账板必须走单板预算缓存兜底，不能误拿合并快照。
    mod = _concept_env(mod)
    mod.g.csnap_led = {
        "day": "2026-11-05",
        "key": "黄金概念|光伏概念",
        "boards": ["黄金概念"],
        "members": ["G1.XSHG"],
        "idx": 1,
        "snap": {"G1.XSHG": {"last_px": 10.0}},
        "ts": time.time(),
        "complete": True,
        "ratio": 1.0,
    }

    assert mod._concept_snap_for("黄金概念", ["G1.XSHG"]) == {"G1.XSHG": {"last_px": 10.0}}

    class _DH:
        def __init__(self):
            self.seen = []

        def cached(self, key, _tag, ttl, factory, **kw):
            self.seen.append(key)
            return factory()

    dh = _DH()
    mod._get_ds = lambda: dh
    out = mod._concept_snap_for("光伏概念", ["P1.XSHG"])
    assert out == {"P1.XSHG": {"preclose_px": 10.0, "last_px": 10.0}}
    assert dh.seen == [("cbsnap", "光伏概念")]


def test_csnap_union_uses_board_union_budget(mod):
    mod = _concept_env(mod)
    dh = _FakeDH()
    mod._get_ds = lambda: dh

    mod._concept_snap_union(["黄金概念"], budget="board_union")
    assert dh.spends[-1] == ("board_union", 0)


def test_source_limit_board_union_fast_and_normal(mod):
    assert mod._source_limit("board_union") == float(mod.BLS["frame_board_union_limit_fast"])
    mod._min_age = lambda: 60
    mod._hhmm = lambda: "10:15"
    assert mod._source_limit("board_union") == float(mod.BLS["frame_board_union_limit"])


def test_csnap_no_top_audit_log(mod):
    mod._csnap_no_top_log("coverage", {
        "boards": 5, "total": 100, "idx": 30, "ratio": 0.3,
        "key_changed": 0, "added_boards": 0, "budget": "board_union",
        "budget_spent": 0, "complete": False,
    })
    assert any("[csnap] no_top reason=coverage" in x and "ratio=0.30" in x for x in mod._logs)


def test_csnap_prewarm_stops_at_coverage(mod):
    mod.g.boards = {"B1": ["A.XSHG"]}
    mod.g.board_type = {"B1": "concept"}
    mod._elastic_top_cand_src = lambda: ["A.XSHG"]
    mod._concept_boards_of = lambda sec: ["B1"]
    mod._concept_snap_union = lambda boards, budget=None, prio=0, force=False: (
        {}, 1.0, {"budget_spent": 1, "key_changed": 0, "total": 10})

    assert mod._csnap_prewarm("09:25") == 1.0
    assert any("[csnap-prewarm] 09:25 boards=1 ratio=1.00 batches=1" in x for x in mod._logs)


def test_m1_surge_na_audit(mod):
    mod._elastic_1m_surge_raw = lambda sec: None
    mod._m1_surge_na_log("A.XSHG", "elastic_top")
    assert any("[m1-surge-na] A.XSHG elastic_top 1m 数据缺失" in x for x in mod._logs)
