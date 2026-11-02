# -*- coding: utf-8 -*-
"""v1.26 打板/扫板场景拆分：A 新题材首板扫板、B 动态唯一扫板、涨停价首帧打板与核心票确认门。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v126_board_sweep_split_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "daily_max_buy": 3,
        "daily_max_board_buy": 2,
        "cold_secs": 0,
        "DO_ORDER": False,
        "EXPECT_ORDER": False,
        "skip_st_pool": True,
        "new_theme_sweep_enabled": True,
        "new_theme_sweep_window_min": 10,
        "vwap_follow_frames": 1,
        "vwap_follow_min_rise": 0.0005,
        "board_first_frame_fresh_sec": 6.0,
        "first_board_buy_enabled": True,
        "first_board_minute": 10,
        "first_board_seal_min": 50000.0,
        "board_rank_enabled": False,
        "firstzt_min_seal": 50000.0,
        "reboard_buy_enabled": True,
        "reboard_until_minute": 30,
        "reboard_seal_min": 50000.0,
        "reboard_l2_big_min": 0.10,
        "core_buy_enabled": True,
        "core_buy_window_min": 30,
        "core_max_lianban": 6,
        "core_sealed_skip": True,
        "buy_score_min": 50.0,
        "board_buy_budget_ratio": 0.20,
        "dyn_sweep_enabled": True,
        "dyn_sweep_window_minute": 30,
        "dyn_sweep_budget_ratio": 0.20,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._fmt_big_ratio = lambda big: '%.1f%%' % (big * 100.0 if big and big > 0 else 0.0)
    m._is_st = lambda sec: False
    m._is_one_word_open = lambda sec: False
    m._block_sealed_buy = lambda sec: False
    m._mid_board_avoid = lambda sec: False
    m._ferment_front_gate = lambda sec: True
    m._two_1m_break = lambda sec: True
    m._limit_up_within_1m = lambda sec: False
    m._l2_big_ratio = lambda sec: 0.15
    m._l2_big_ok = lambda sec: True
    m._lb_senti_gate_apply = lambda sec, action: True
    m._new_themes_of = lambda sec: ["THS:新概念"]
    m.g = SimpleNamespace(
        daily=m._new_daily(),
        spot={},
        near_scan={},
        pool_static=[],
        watch=[],
        exp_file={},
        first_zt={},
        buy_log={},
        vwap_track={},
        skip_log_ts={},
    )
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def test_vwap_follow_up_needs_rising_frames(mod):
    mod.BLS["vwap_follow_frames"] = 2
    mod.g.spot["A"] = {"last_px": 10.5, "wavg_px": 10.3}
    mod.g.vwap_track["A"] = {"vwap": 10.28, "cnt": 1, "ts": time.time()}
    assert mod._vwap_follow_up("A") is True

    mod.g.spot["B"] = {"last_px": 10.0, "wavg_px": 10.5}
    assert mod._vwap_follow_up("B") is False   # 现价低于均价


def test_new_theme_sweep_a_orders_sweep_mode(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio)) or True)
    mod.g.spot["A"] = {"last_px": 10.5, "up_px": 11.0, "wavg_px": 10.3}
    mod.g.near_scan = {"A": {"chg": 8.0}}
    mod._min_age = lambda: 5

    mod._try_new_theme_sweep(_ctx())

    assert calls == [("A", "sweep", 0.20)]
    assert "A" in mod.g.daily["bought_board"]


def test_new_theme_sweep_a_requires_l2_net_10pct(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode)) or True)
    mod.g.spot["A"] = {"last_px": 10.5, "up_px": 11.0, "wavg_px": 10.3}
    mod.g.near_scan = {"A": {"chg": 8.0}}
    mod._min_age = lambda: 5
    mod._l2_big_ratio = lambda sec: 0.05
    mod._l2_big_ok = lambda sec: False

    mod._try_new_theme_sweep(_ctx())

    assert calls == []


def test_dyn_sweep_b_orders_sweep_mode(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio)) or True)
    mod._dyn_unq_auction_unique = lambda sec: True
    mod._dyn_unq_confirmed = lambda sec: True
    mod._min_age = lambda: 5
    mod._order_limit = lambda sec, side, mode: 10.8
    mod.g.exp_file = {"A": {"side": "buy"}}
    mod.g.spot["A"] = {"last_px": 10.5, "up_px": 11.0}
    st = {"uniq": {"A": {"surge_cnt": 2}}, "swept": {}}

    mod._try_dyn_sweep(_ctx(), st)

    assert calls == [("A", "sweep", 0.20)]
    assert "A" in st["swept"]


def test_first_board_tx_first_frame_exempts_seal_gate(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}
    mod.g.first_zt = {"A": {"src": "tx", "ts": time.time(), "break_cnt": 0, "ms": 1}}
    mod._is_first_board = lambda sec: True
    mod._seal_metrics = lambda sec: (1000.0, 2)   # 封单 < 5万，tx 首帧仍放行
    mod._l2_big_ratio = lambda sec: -1.0
    mod._l2_big_ok = lambda sec: False
    mod._board_top_gainer = lambda sec: True
    mod._board_first_zt = lambda sec: True
    mod._order_limit = lambda sec, side, mode: 11.0
    mod._sector_chg = lambda sec: 0.1
    mod._tags = lambda sec: ["CORE"]
    mod._ft_state_str = lambda sec: "src:tx ms:1 bc:0 seal:0"
    mod._min_age = lambda: 3

    mod._try_first_board_buy(_ctx(), "A", rank_secs=["A"])

    assert len(calls) == 1 and calls[0][1] == "board"


def test_first_board_snap_fallback_keeps_seal_gate(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode)) or True)
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}
    mod.g.first_zt = {"A": {"src": "snap", "ts": time.time(), "break_cnt": 0}}
    mod._is_first_board = lambda sec: True
    mod._seal_metrics = lambda sec: (1000.0, 2)
    mod._l2_big_ratio = lambda sec: -1.0
    mod._l2_big_ok = lambda sec: False
    mod._board_top_gainer = lambda sec: True
    mod._board_first_zt = lambda sec: True
    mod._min_age = lambda: 3

    mod._try_first_board_buy(_ctx(), "A", rank_secs=["A"])

    assert calls == []


def test_board_first_frame_ok_freshness(mod):
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.g.first_zt = {"A": {"ts": time.time()}}
    assert mod._board_first_frame_ok("A") is True

    mod.g.first_zt["A"]["ts"] = time.time() - 10.0
    assert mod._board_first_frame_ok("A") is False

    mod.g.spot["A"]["last_px"] = 10.9
    mod.g.first_zt["A"]["ts"] = time.time()
    assert mod._board_first_frame_ok("A") is False


def test_core_confirm_gate_l2_net_can_pass(mod):
    mod._two_1m_break = lambda sec: False
    mod._limit_up_within_1m = lambda sec: False
    mod._below_vwap_confirm = lambda sec: False
    mod._l2_big_ok = lambda sec: True
    assert mod._core_confirm_ok("A") is True

    mod._l2_big_ok = lambda sec: False
    assert mod._core_confirm_ok("A") is False


def test_core_buy_requires_first_frame_and_boards(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio)) or True)
    mod._min_age = lambda: 5
    mod._pool = lambda: ["A"]
    mod._tags = lambda sec: ["CORE"]
    mod._limitup_days = lambda sec: 1
    mod._core_confirm_ok = lambda sec: True
    mod._board_first_frame_ok = lambda sec: True
    mod.score_now = lambda sec: 60.0
    mod._buy_red_ok = lambda sec: True
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.g.first_zt = {"A": {"ts": time.time()}}

    mod.try_core_buy(_ctx())

    assert calls == [("A", "board", 0.20)]
    assert "A" in mod.g.daily["bought_core"]


def test_core_buy_skips_without_first_frame(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode)) or True)
    mod._pool = lambda: ["A"]
    mod._tags = lambda sec: ["CORE"]
    mod._limitup_days = lambda sec: 1
    mod._core_confirm_ok = lambda sec: True
    mod._board_first_frame_ok = lambda sec: False
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.g.first_zt = {"A": {"ts": time.time() - 10.0}}

    mod.try_core_buy(_ctx())

    assert calls == []


def test_sweep_pending_gets_break_protection_base(mod):
    mod.BLS["DO_ORDER"] = True
    mod.order = lambda sec, amt, limit_price=None: "ent1"
    mod._signal = lambda sec, side, qty, limit, mode, note, ent='', status='': None
    mod._buy_commit_add = lambda sec, qty, limit: None
    mod._rt_lag_info = lambda sec: (0, 0)
    mod._log_order_limit = lambda sec, limit: None
    mod._size_cash = lambda context: 10000.0
    mod._calc_buy_qty = lambda context, sec, px, ratio: 100
    mod._buy_pos_cap_qty = lambda context, sec, qty, limit: 100
    mod._qty_calc_log = lambda context, sec, tag: None
    mod._seal_metrics = lambda sec: (100.0, 1)
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "wavg_px": 10.5}
    mod.g.first_zt = {"A": {"break_cnt": 2, "src": "tx", "ts": time.time()}}
    mod.g.pending = {}

    ok = mod.place_order(_ctx(), "A", "buy", mode="sweep")

    assert ok is True
    assert mod.g.pending["A"]["mode"] == "sweep"
    assert mod.g.pending["A"]["break_cnt_at_send"] == 2
