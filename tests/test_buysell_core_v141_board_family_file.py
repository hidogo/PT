# -*- coding: utf-8 -*-
"""v1.41 云端家族映射：board_family_latest.csv 人工覆盖层、自动映射兜底、迟到重建、损坏容错回归测试。"""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v141_family_test", STRATEGY_PATH)
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


def _concept_env(mod):
    mod.BLS["board_family_min_overlap"] = 2
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
    return mod


def _write_fam(tmp_path, text):
    fp = tmp_path / "board_family_latest.csv"
    fp.write_text(text, encoding="utf-8")
    mod_path = lambda: [str(tmp_path) + os.sep]
    return fp, mod_path


def test_load_board_family_file(mod, tmp_path):
    _, roots = _write_fam(
        tmp_path,
        "board_name,family_name\n"
        "黄金概念,黄金/有色/资源\n"
        "稀土永磁,黄金/有色/资源\n",
    )
    mod._research_roots = roots
    n = mod._load_board_family()
    assert n == 2
    assert mod.g.board_family_file_map == {
        "黄金概念": "黄金/有色/资源",
        "稀土永磁": "黄金/有色/资源",
    }


def test_board_family_file_override_prefers_file(mod, tmp_path):
    mod = _concept_env(mod)
    _, roots = _write_fam(
        tmp_path,
        "board_name,family_name\n"
        "黄金概念,黄金/有色/资源\n"
        "光伏概念,测试族\n",
    )
    mod._research_roots = roots
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"
    assert mod._board_family_of("光伏概念") == "测试族"
    assert mod._board_family_of("半导体概念") == "半导体概念"


def test_board_family_file_missing_fallback_auto(mod):
    mod = _concept_env(mod)
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"
    assert mod._board_family_of("光伏概念") == "光伏/风电/电力/储能"
    assert mod._board_family_of("半导体概念") == "半导体概念"
    assert mod.g.board_family_file_map is None


def test_board_family_reload_after_zt_lianban_clear(mod, tmp_path):
    mod = _concept_env(mod)
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"
    _, roots = _write_fam(tmp_path, "board_name,family_name\n黄金概念,测试族\n")
    mod._research_roots = roots
    mod.g.board_family_map = None   # 模拟 _load_zt_lianban 重读清缓存
    assert mod._board_family_of("黄金概念") == "测试族"


def test_board_family_late_file_clears_cache(mod, tmp_path):
    mod = _concept_env(mod)
    assert mod._board_family_of("黄金概念") == "黄金/有色/资源"
    assert mod.g.board_family_map is not None
    _, roots = _write_fam(tmp_path, "board_name,family_name\n黄金概念,测试族\n")
    mod._research_roots = roots
    assert mod._load_board_family() == 1
    assert mod.g.board_family_map is None   # 09:31 迟到上传 -> 自动重建
    assert mod._board_family_of("黄金概念") == "测试族"


def test_board_family_file_invalid_header(mod, tmp_path):
    _, roots = _write_fam(tmp_path, "bad,header\n黄金概念,黄金/有色/资源\n")
    mod._research_roots = roots
    assert mod._load_board_family() == 0
    assert mod.g.board_family_file_map is None


def test_board_family_file_bad_rows_skipped(mod, tmp_path):
    _, roots = _write_fam(
        tmp_path,
        "board_name,family_name\n"
        "黄金概念,黄金/有色/资源\n"
        ",空族名\n"
        "稀土永磁,\n",
    )
    mod._research_roots = roots
    n = mod._load_board_family()
    assert n == 1
    assert mod.g.board_family_file_map == {"黄金概念": "黄金/有色/资源"}
