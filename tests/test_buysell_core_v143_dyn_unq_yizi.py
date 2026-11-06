# -*- coding: utf-8 -*-
"""v1.43 动态唯一扩充：同身位大单一字板竞品豁免 + 超预期确认 + 换手打板可参与唯一。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v143_dyn_unq_yizi_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "dyn_unq_enabled": True,
        "dyn_unq_theme_mode": True,
        "dyn_unq_min_level": 2,
        "dyn_unq_min_members": 3,
        "dyn_unq_min_covered": 0.8,
        "dyn_unq_sep_chg_gap": 2.0,
        "dyn_unq_max_active": 3,
        "dyn_unq_pool_cache_sec": 15,
        "dyn_unq_sep_recheck_sec": 15,
        "dyn_unq_yizi_extend_enabled": True,
        "dyn_unq_yizi_extend_seal_min": 2000000.0,
        "dyn_unq_yizi_extend_big_min": 0.10,
        "dyn_unq_yizi_extend_confirm": True,
        "dyn_unq_yizi_extend_playable": True,
        "dyn_sweep_enabled": True,
        "dyn_sweep_window_minute": 30,
        "dyn_sweep_budget_ratio": 0.20,
        "daily_max_buy": 3,
        "daily_max_board_buy": 2,
        "cold_secs": 0,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._get_snapshot_many = lambda codes, cap: {}
    m._new_themes_of = lambda sec: []
    m._is_one_word_open = lambda sec: False
    m._sealed_at_limit = lambda sec: False
    m._seal_metrics = lambda sec: (0.0, 0)
    m._l2_big_ratio = lambda sec: -1.0
    m._mid_board_avoid = lambda sec: False
    m._block_sealed_buy = lambda sec: False
    m._exp_rt_status = lambda sec: ("confirmed_exceed", "intraday_exceed")
    m.g = SimpleNamespace(
        daily=m._new_daily(),
        spot={},
        zt_lianban={},
        zt_theme={},
        zt_themes_of={},
        zt_new_cache={"ts": 0.0, "data": {}},
        boards={},
        stock_boards={},
        first_zt={},
        buy_log={},
        skip_log_ts={},
        dyn_unq=None,
        dyn_unq_pool_cache={},
    )
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def _env(mod, peers=None):
    # peers: [(code, chg_pct, break, board_cnt)]，默认 B 为同身位未分离竞品
    members = ["A", "B", "C"]
    mod.g.zt_themes_of["A"] = ["T"]
    for c in members:
        mod.g.zt_themes_of[c] = ["T"]
        mod.g.spot[c] = {"last_px": 10.0, "preclose_px": 10.0, "up_px": 10.6}
    mod.g.zt_theme["T"] = {"members": set(members), "max_board": 2, "count": 3, "rank": 2}
    mod.g.zt_lianban = {
        "A": {"board_cnt": 2},
        "B": {"board_cnt": 2},
        "C": {"board_cnt": 1},
    }
    for code, chg, brk, lvl in (peers or [("B", 3.0, False, 2)]):
        mod.g.first_zt[code] = {"ts": time.time(), "break": brk}
        mod.g.spot[code] = {"last_px": 10.0 + chg / 100.0, "preclose_px": 10.0, "up_px": 10.6}
        mod.g.zt_lianban[code] = {"board_cnt": lvl}
    mod.g.first_zt["A"] = {"ts": time.time(), "break": False}
    mod.g.spot["A"] = {"last_px": 10.04, "preclose_px": 10.0, "up_px": 10.6}


def _eval(mod):
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    return st["uniq"].get("A") or {}


def test_yizi_extend_grants_playable_unique(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    u = _eval(mod)
    assert u.get("uniq") is True
    assert u.get("extend_yizi") is True
    assert u.get("confirm") is True
    assert u.get("yizi_peers") == ["B"]


def test_yizi_extend_big_ratio_fallback(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (0.0, 0)
    mod._l2_big_ratio = lambda sec: 0.18 if sec == "B" else -1.0
    u = _eval(mod)
    assert u.get("uniq") is True
    assert u.get("extend_yizi") is True


def test_yizi_extend_requires_intraday_confirm(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    mod._exp_rt_status = lambda sec: ("pending_meet", "observe")
    u = _eval(mod)
    assert u.get("uniq") is False
    assert u.get("same") == ["B"]


def test_yizi_extend_requires_playable(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: True   # 本票一字：无参与机会
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    u = _eval(mod)
    assert u.get("uniq") is False
    assert u.get("same") == ["B"]


def test_yizi_extend_peer_mid_blocks(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    mod._mid_board_avoid = lambda sec: sec == "B"
    u = _eval(mod)
    assert u.get("uniq") is False
    assert u.get("same") == ["B"]


def test_yizi_extend_peer_not_big_blocks(mod):
    _env(mod)
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (10000.0, 3) if sec == "B" else (0.0, 0)
    u = _eval(mod)
    assert u.get("uniq") is False
    assert u.get("same") == ["B"]


def test_yizi_extend_other_same_peer_blocks(mod):
    _env(mod, peers=[("B", 3.0, False, 2), ("C", 5.0, False, 2)])
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    u = _eval(mod)
    assert u.get("uniq") is False
    assert "B" not in u.get("same", [])
    assert u.get("yizi_peers") == ["B"]
    assert "C" in u.get("same", [])


def test_yizi_extend_disable_keeps_old_behavior(mod):
    _env(mod)
    mod.BLS["dyn_unq_yizi_extend_enabled"] = False
    mod._is_one_word_open = lambda sec: sec == "B"
    mod._sealed_at_limit = lambda sec: False
    mod._seal_metrics = lambda sec: (5000000.0, 20) if sec == "B" else (0.0, 0)
    u = _eval(mod)
    assert u.get("uniq") is False
    assert u.get("same") == ["B"]


def test_dyn_sweep_b_yizi_extend_skips_auction_unique(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio)) or True)
    mod._dyn_unq_auction_unique = lambda sec: False   # 竞价非唯一：扩充唯一应豁免
    mod._dyn_unq_confirmed = lambda sec: True
    mod._dyn_unq_theme_rank_ok = lambda sec: True
    mod._min_age = lambda: 5
    mod._order_limit = lambda sec, side, mode: 10.8
    mod._two_1m_break = lambda sec: True
    mod._limit_up_within_1m = lambda sec: False
    mod.g.exp_file = {"A": {"side": "buy"}}
    mod.g.spot["A"] = {"last_px": 10.5, "up_px": 11.0}
    st = {"uniq": {"A": {"surge_cnt": 2, "extend_yizi": True}}, "swept": {}}
    mod._try_dyn_sweep(_ctx(), st)
    assert calls == [("A", "sweep", 0.20)]
    assert "A" in st["swept"]
