# -*- coding: utf-8 -*-
"""v1.30 盘中动态唯一题材化重构 + T+1 当日买入保护持久化。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v130_theme_unique_t1_test", STRATEGY_PATH)
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
        "dyn_unq_surge_na_max": 0.5,
        "dyn_unq_theme_rank_max": 3,
        "t1_protect_enabled": True,
        "t1_protect_open_drop": 0.02,
        "t1_protect_strong_open": 3.0,
        "t1_protect_consume_until_minute": 10,
        "t1_pending_save_sec": 60.0,
        "green_open_drop": -5.0,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m._sn = lambda sec: sec
    m._get_snapshot_many = lambda codes, cap: {}
    m._new_themes_of = lambda sec: []
    m._hold_arb_log = lambda sec, msg: None
    m._try_dyn_sweep = lambda context, st=None: None
    m._do_sell = lambda *a, **k: None
    m._auction_change = lambda sec: 0.0
    m._p2e_core_sell_check = lambda sec: (False, '')
    m._p7a_check = lambda sec, amt: None
    m._p7b_check = lambda sec, amt: None
    m._p7d_check = lambda sec, amt: None
    m._lb_senti_cut_hold = lambda sec: None
    m._role_tolerance = lambda sec: {'green_tol': 1.0, 'stop_adj': 1.0,
                                     'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    m._sealed_now = lambda sec: False
    m._today_zt = lambda sec: False
    m.get_stop_loss_pct = lambda sec: 0.05
    m._sellable_source = lambda: {}
    m.g = SimpleNamespace(
        daily=m._new_daily(),
        spot={},
        zt_lianban={},
        zt_theme={},
        zt_themes_of={},
        zt_new_cache={'ts': 0.0, 'data': {}},
        boards={},
        stock_boards={},
        first_zt={},
        buy_log={},
        skip_log_ts={},
        dyn_unq=None,
        dyn_unq_pool_cache={},
        t1_pending_sell={},
        t1_pending_log_ts={},
        t1_pending_save_ts=0.0,
        bought_qty={},
    )
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def _theme_env(mod, sec, peer=None, peer_chg=None, peer_break=False, higher=None):
    mod.g.zt_themes_of[sec] = ["T"]
    members = ["A", "B", "C"]
    mod.g.zt_theme["T"] = {"members": set(members), "max_board": 2, "count": 3, "rank": 2}
    for c in members:
        mod.g.zt_themes_of[c] = ["T"]
        mod.g.spot[c] = {"last_px": 10.0, "preclose_px": 10.0, "up_px": 10.6}
    mod.g.zt_lianban = {
        "A": {"board_cnt": 2},
        "B": {"board_cnt": 2},
        "C": {"board_cnt": 1},
    }
    if higher:
        mod.g.zt_lianban[higher] = {"board_cnt": 3}
        mod.g.zt_themes_of[higher] = ["T"]
        mod.g.spot[higher] = {"last_px": 10.0, "preclose_px": 10.0, "up_px": 10.6}
    if peer:
        mod.g.first_zt[peer] = {"ts": time.time(), "break": peer_break}
    if peer_chg is not None:
        mod.g.spot[peer] = {"last_px": 10.0 + peer_chg / 100.0, "preclose_px": 10.0, "up_px": 10.6}
    mod.g.first_zt[sec] = {"ts": time.time(), "break": False}
    mod.g.spot[sec] = {"last_px": 10.04, "preclose_px": 10.0, "up_px": 10.6}


def test_uniq_theme_requires_level(mod):
    mod.g.zt_themes_of["A"] = ["T"]
    mod.g.zt_theme["T"] = {"members": {"A", "B", "C"}, "max_board": 1, "count": 3, "rank": 1}
    for c in ("A", "B", "C"):
        mod.g.zt_themes_of[c] = ["T"]
        mod.g.spot[c] = {"last_px": 10.0, "preclose_px": 10.0, "up_px": 10.6}
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    assert "A" not in st["uniq"]


def test_uniq_theme_member_too_small(mod):
    mod.g.zt_themes_of["A"] = ["T"]
    mod.g.zt_theme["T"] = {"members": {"A"}, "max_board": 2, "count": 1, "rank": 1}
    mod.g.zt_lianban = {"A": {"board_cnt": 1}}
    mod.g.spot["A"] = {"last_px": 10.04, "preclose_px": 10.0, "up_px": 10.6}
    mod.g.first_zt["A"] = {"ts": time.time(), "break": False}
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    assert "A" not in st["uniq"]


def test_uniq_theme_covered_low(mod):
    _theme_env(mod, "A", peer="B", peer_chg=1.0)
    mod.g.spot["C"] = {}
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    assert "A" not in st["uniq"]


def test_uniq_theme_same_peer_blocks(mod):
    _theme_env(mod, "A", peer="B", peer_chg=3.0)
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    u = st["uniq"].get("A") or {}
    assert u.get("uniq") is False
    assert u.get("same")


def test_uniq_theme_separated_peer_allows(mod):
    _theme_env(mod, "A", peer="B", peer_chg=1.0, peer_break=True)
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    u = st["uniq"].get("A") or {}
    assert u.get("uniq") is True
    assert u.get("unique_ts")


def test_uniq_theme_higher_alive_blocks(mod):
    _theme_env(mod, "A", peer="B", peer_chg=1.0, peer_break=True, higher="D")
    mod.g.first_zt["D"] = {"ts": time.time(), "break": False}
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    u = st["uniq"].get("A") or {}
    assert u.get("uniq") is False
    assert u.get("higher") is True


def _follow_env(mod):
    members = ["A", "B", "C", "D"]
    mod.g.zt_theme["T"] = {"members": set(members), "max_board": 2, "count": 4, "rank": 2}
    for c in members:
        mod.g.zt_themes_of[c] = ["T"]
        mod.g.spot[c] = {"last_px": 10.01, "preclose_px": 10.0, "up_px": 10.6}
    mod.g.zt_lianban = {
        "A": {"board_cnt": 2},
        "B": {"board_cnt": 1},
        "C": {"board_cnt": 1},
        "D": {"board_cnt": 1},
    }
    mod.g.first_zt["A"] = {"ts": time.time(), "break": False}
    mod.g.spot["A"] = {"last_px": 10.04, "preclose_px": 10.0, "up_px": 10.6}


def test_follow_confirm_uses_theme_pool(mod):
    _follow_env(mod)
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    u = st["uniq"]["A"]
    mod._dyn_unq_surge_raw = lambda sec: 2.0
    mod._dyn_unq_eval_follow("A", st, u)
    assert u.get("confirm") is True


def test_follow_confirm_surge_na_blocks(mod):
    _follow_env(mod)
    st = {"uniq": {}}
    mod._dyn_unq_eval_uniq("A", st, time.time())
    u = st["uniq"]["A"]
    mod._dyn_unq_surge_raw = lambda sec: None
    mod._dyn_unq_eval_follow("A", st, u)
    assert u.get("confirm") is False
    assert u.get("surge_na") == 3


def test_dyn_unq_max_active_cap(mod):
    st = {"day": "2026-11-03", "auction": {}, "uniq": {}, "swept": {}}
    now = time.time()
    for i, c in enumerate(("A", "B", "C", "D")):
        st["uniq"][c] = {"uniq": True, "level": 3, "unique_ts": now + i,
                         "theme": "T", "confirm": False, "confirm_ts": 0,
                         "members": [], "surge_cnt": 0}
    mod.g.dyn_unq = st
    mod.g.exp_file = {}
    mod._dyn_unq_state = lambda: st
    mod._min_age = lambda: 5
    mod._dyn_unq_confirmed = lambda sec: False
    mod._try_dyn_unq(_ctx())
    assert len(st["uniq"]) <= 3
    assert "A" in st["uniq"]


def test_dyn_unq_theme_rank_ok(mod):
    mod.g.zt_themes_of["A"] = ["T1", "THS:新概念"]
    mod.g.zt_theme["T1"] = {"members": {"A"}, "rank": 2}
    assert mod._dyn_unq_theme_rank_ok("A") is True
    mod.g.zt_theme["T1"]["rank"] = 5
    assert mod._dyn_unq_theme_rank_ok("A") is False


def test_t1_protect_capture_records(mod):
    mod.g.daily["bought"] = ["600001.XSHG"]
    mod.g.bought_qty = {"600001.XSHG": 100}
    mod.g.first_zt["600001.XSHG"] = {"break": True}
    mod.my_cost = lambda sec, positions: 10.0
    mod.last_px = lambda sec: 10.0
    mod.get_trading_day = lambda: "2026-11-03"
    mod._t1_protect_capture("600001.XSHG", "600001", {"600001": {"enable_amount": 0}})
    rec = mod.g.t1_pending_sell.get("600001.XSHG") or {}
    assert rec.get("day") == "2026-11-03"
    assert rec.get("qty") == 100
    assert "BREAK" in rec.get("triggers", [])


def test_t1_protect_consume_weak_open_sells(mod):
    mod.g.t1_pending_sell["600001.XSHG"] = {
        "day": "2026-10-30", "triggers": ["BREAK"], "qty": 100,
        "cost": 10.0, "px": 10.0, "note": "BREAK"}
    positions = {"600001": {"enable_amount": 100, "amount": 100}}
    mod._sellable_source = lambda: positions
    mod._auction_change = lambda sec: -3.0
    mod._min_age = lambda: 5
    mod.last_px = lambda sec: 9.7
    mod.get_trading_day = lambda: "2026-11-03"
    calls = []
    mod._do_sell = lambda context, sec, qty, note, urgent=False, mode=None: calls.append((sec, qty, note))
    mod._t1_protect_consume(_ctx())
    assert len(calls) == 1
    assert calls[0][0] == "600001.XSHG"
    assert calls[0][2].startswith("T1_protect_weak_open")
    assert "600001.XSHG" not in mod.g.t1_pending_sell


def test_t1_protect_consume_strong_open_clears(mod):
    mod.g.t1_pending_sell["600001.XSHG"] = {
        "day": "2026-10-30", "triggers": ["BREAK"], "qty": 100,
        "cost": 10.0, "px": 10.0, "note": "BREAK"}
    positions = {"600001": {"enable_amount": 100, "amount": 100}}
    mod._sellable_source = lambda: positions
    mod._auction_change = lambda sec: 5.0
    mod._min_age = lambda: 5
    mod.get_trading_day = lambda: "2026-11-03"
    calls = []
    mod._do_sell = lambda context, sec, qty, note, urgent=False, mode=None: calls.append((sec, qty, note))
    mod._t1_protect_consume(_ctx())
    assert calls == []
    assert "600001.XSHG" not in mod.g.t1_pending_sell


def test_t1_protect_consume_window_end_clears(mod):
    mod.g.t1_pending_sell["600001.XSHG"] = {
        "day": "2026-10-30", "triggers": ["BREAK"], "qty": 100,
        "cost": 10.0, "px": 10.0, "note": "BREAK"}
    positions = {"600001": {"enable_amount": 100, "amount": 100}}
    mod._sellable_source = lambda: positions
    mod._auction_change = lambda sec: 0.0
    mod._min_age = lambda: 12
    mod.get_trading_day = lambda: "2026-11-03"
    calls = []
    mod._do_sell = lambda context, sec, qty, note, urgent=False, mode=None: calls.append((sec, qty, note))
    mod._t1_protect_consume(_ctx())
    assert calls == []
    assert "600001.XSHG" not in mod.g.t1_pending_sell
