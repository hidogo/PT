# -*- coding: utf-8 -*-
"""v1.24 竞价-开盘-10:00 跌停题材因子：全市场跌停归集、题材/概念回避与减分消费。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v124_ld_factor_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "ld_senti_enabled": True,
        "ld_theme_soft_min": 1,
        "ld_theme_hard_min": 2,
        "ld_theme_penalty": 0.8,
        "ld_zt_ld_hard_enabled": True,
        "ld_market_soft_n": 20,
        "ld_market_penalty": 0.3,
        "ld_sort_penalty": 1.5,
        "exp_direction_enabled": True,
        "exp_direction_attack_bonus": 0.8,
        "exp_direction_avoid_hard_skip": True,
        "exp_direction_hot_front_only": True,
        "exp_direction_rotate_leader_exception": True,
        "exp_direction_log": False,
        "lb_senti_gate_all_buys_enabled": True,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m.g = SimpleNamespace(
        zt_lianban={"600002.XSHG": {"board_cnt": 3}},
        zt_themes_of={"600002.XSHG": ["机器人"]},
        boards={"跌停概念": ["600002.XSHG"]},
        board_type={"跌停概念": "concept"},
        stock_boards={"600002.XSHG": ["跌停概念"]},
        lb_senti={},
        pool_all=[],
        pool_day="",
    )
    m._hhmm = lambda: "09:40"
    m._zt_themes_of = lambda sec: list(m.g.zt_themes_of.get(sec) or [])
    m._new_themes_of = lambda sec: []
    m._concept_boards_of = lambda sec: list(m.g.stock_boards.get(sec) or [])
    return m


def _ld(ld_n=5, theme_ld=None, concept_ld=None, zt_ld_n=1):
    return {
        "ld_n": ld_n,
        "ld_codes": [],
        "theme_ld": theme_ld or {},
        "concept_ld": concept_ld or {},
        "zt_ld_n": zt_ld_n,
    }


def test_fetch_market_red_counts_limit_down_and_themes(mod):
    mod.get_snapshot = lambda codes: {
        "600001.XSHG": {"preclose_px": 10.0, "last_px": 11.0},   # 上涨
        "600002.XSHG": {"preclose_px": 10.0, "last_px": 9.0},    # 主板跌停 -10%
        "300001.XSHE": {"preclose_px": 20.0, "last_px": 16.0},   # 创业板跌停 -20%
        "600003.XSHG": {"preclose_px": 10.0, "last_px": 10.0},   # 平盘
    }
    out = mod._fetch_market_red(
        ["600001.XSHG", "600002.XSHG", "300001.XSHE", "600003.XSHG"])
    assert out["up"] == 1 and out["dn"] == 2
    assert out["red"] == pytest.approx(1.0 / 3.0)
    assert out["ld_n"] == 2
    assert out["zt_ld_n"] == 1
    assert out["theme_ld"] == {"机器人": 1}
    assert out["concept_ld"] == {"跌停概念": 1}


def test_ld_theme_hit_old_theme_ld_is_hard(mod):
    mod._market_ld_senti = lambda force_fetch=False: _ld(theme_ld={"机器人": 1})
    hit = mod._ld_theme_hit("600002.XSHG")
    assert hit is not None
    assert hit["hard"] is True
    assert hit["n"] == 1 and hit["n_old"] == 1


def test_ld_theme_hit_concept_soft_then_hard(mod):
    mod._zt_themes_of = lambda sec: []
    mod._market_ld_senti = lambda force_fetch=False: _ld(concept_ld={"跌停概念": 1})
    hit = mod._ld_theme_hit("600002.XSHG")
    assert hit["hard"] is False and hit["n"] == 1 and hit["n_new"] == 1

    mod._market_ld_senti = lambda force_fetch=False: _ld(concept_ld={"跌停概念": 2})
    hit = mod._ld_theme_hit("600002.XSHG")
    assert hit["hard"] is True


def test_ld_theme_hit_missing_data_returns_none(mod):
    mod._market_ld_senti = lambda force_fetch=False: None
    assert mod._ld_theme_hit("600002.XSHG") is None


def test_ld_theme_hit_before_auction_not_consumed(mod):
    mod._hhmm = lambda: "09:20"
    mod._market_ld_senti = lambda force_fetch=False: _ld(theme_ld={"机器人": 5})
    assert mod._ld_theme_hit("600002.XSHG") is None


def test_exp_direction_hard_ld_becomes_avoid(mod):
    mod._lb_senti_phase = lambda: {"phase": "high_continue"}
    mod._lb_senti_tier = lambda sec: "mid"
    mod._dyn_theme_status = lambda: {"机器人": {"leader": "600002.XSHG", "max_board_dyn": 3}}
    mod._dyn_theme_ferment = lambda: {}
    mod._ld_theme_hit = lambda sec, old_themes=None, new_themes=None: {
        "hard": True, "n": 2, "n_old": 1, "theme": "机器人", "n_new": 1}

    ctx = mod._exp_direction_eval("600002.XSHG")
    assert ctx["kind"] == "avoid"
    assert ctx["hard_skip"] is True
    assert ctx["reason"].startswith("theme_limit_down")


def test_exp_direction_soft_ld_deducts_score(mod):
    mod._lb_senti_phase = lambda: {"phase": "high_continue"}
    mod._lb_senti_tier = lambda sec: "mid"
    mod._dyn_theme_status = lambda: {"机器人": {"leader": "600002.XSHG", "max_board_dyn": 3}}
    mod._dyn_theme_ferment = lambda: {}
    mod._ld_theme_hit = lambda sec, old_themes=None, new_themes=None: {
        "hard": False, "n": 1, "n_old": 0, "theme": "跌停概念", "n_new": 1}
    mod._market_ld_senti = lambda force_fetch=False: _ld(ld_n=3)

    ctx = mod._exp_direction_eval("600002.XSHG")
    assert ctx["kind"] == "attack_high"
    assert ctx["score"] == pytest.approx(0.0)
    assert ctx["ld_penalized"] is True


def test_exp_direction_market_ld_spread_deducts_score(mod):
    mod._lb_senti_phase = lambda: {"phase": "high_continue"}
    mod._lb_senti_tier = lambda sec: "mid"
    mod._dyn_theme_status = lambda: {"机器人": {"leader": "600002.XSHG", "max_board_dyn": 3}}
    mod._dyn_theme_ferment = lambda: {}
    mod._ld_theme_hit = lambda sec, old_themes=None, new_themes=None: None
    mod._market_ld_senti = lambda force_fetch=False: _ld(ld_n=25)

    ctx = mod._exp_direction_eval("600002.XSHG")
    assert ctx["score"] == pytest.approx(0.5)
    assert ctx["market_ld_n"] == 25


def test_gate_apply_hard_ld_blocks(mod):
    mod._ld_theme_hit = lambda sec: {"hard": True, "n": 2, "n_old": 1, "theme": "机器人", "n_new": 1}
    mod._lb_senti_buy_gate = lambda sec: (True, "normal")
    mod._lb_gate_seen = lambda sec, note, action: None
    assert mod._lb_senti_gate_apply("600002.XSHG", "first_board") is False


def test_gate_apply_soft_ld_still_allows(mod):
    mod._ld_theme_hit = lambda sec: {"hard": False, "n": 1, "n_old": 0, "theme": "跌停概念", "n_new": 1}
    mod._lb_senti_buy_gate = lambda sec: (True, "normal")
    mod._lb_gate_seen = lambda sec, note, action: None
    assert mod._lb_senti_gate_apply("600002.XSHG", "first_board") is True


def test_theme_sort_bonus_ld_hard_zero(mod):
    mod._ld_theme_hit = lambda code: {"hard": True, "n": 2, "n_old": 1, "theme": "机器人", "n_new": 1}
    mod._dyn_theme_status = lambda: {
        "机器人": {"leader": "600002.XSHG", "max_board_dyn": 3, "rank": 1, "alive_count": 2}}
    mod._dyn_theme_ferment = lambda: {}
    assert mod._zt_theme_sort_bonus("600002.XSHG") == 0.0


def test_theme_sort_bonus_ld_soft_deducts(mod):
    mod._dyn_theme_status = lambda: {
        "机器人": {"leader": "600002.XSHG", "max_board_dyn": 3, "rank": 1, "alive_count": 2}}
    mod._dyn_theme_ferment = lambda: {}
    mod._ld_theme_hit = lambda code: None
    base = mod._zt_theme_sort_bonus("600002.XSHG")
    assert base == pytest.approx(3.0)
    mod._ld_theme_hit = lambda code: {"hard": False, "n": 1, "n_old": 0, "theme": "跌停概念", "n_new": 1}
    assert mod._zt_theme_sort_bonus("600002.XSHG") == pytest.approx(base - 1.5)


def test_ld_senti_snapshot_writes_stage(mod):
    mod.get_trading_day = lambda: "20261102"
    mod._market_ld_senti = lambda force_fetch=False: _ld(
        ld_n=8, theme_ld={"机器人": 1}, concept_ld={"跌停概念": 2}, zt_ld_n=1)
    rec = mod._ld_senti_snapshot("auction")
    assert rec is not None and rec["n"] == 8 and rec["zt_ld_n"] == 1
    st = mod._lb_senti_state()
    assert st["ld"]["auction"]["n"] == 8
    assert st["ld"]["last"] == "auction"


def test_ld_senti_snapshot_missing_data_keeps_no_stage(mod):
    mod.get_trading_day = lambda: "20261102"
    mod._market_ld_senti = lambda force_fetch=False: None
    assert mod._ld_senti_snapshot("open") is None
    st = mod._lb_senti_state()
    assert "open" not in st["ld"]
