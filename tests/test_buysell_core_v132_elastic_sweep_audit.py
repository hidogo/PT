# -*- coding: utf-8 -*-
"""v1.32 扫板A弹性分流 + 三态逐票审计 + hist1d 预温保活 + 扫板A ld 快照/T+1 优先 + senti-hist 主题清单。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v132_elastic_sweep_audit_test", STRATEGY_PATH)
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
        "elastic_from_sweep_enabled": True,
        "elastic_from_sweep_limit_ratio": 0.99,
        "elastic_from_sweep_ratio": 0.10,
        "elastic_arb_enabled": True,
        "elastic_arb_min_change": 6.0,
        "elastic_arb_max_change": 10.0,
        "elastic_arb_min_change_bse": 8.0,
        "elastic_arb_max_change_bse": 15.0,
        "board_buy_budget_ratio": 0.20,
        "ordinary_buy_ratio": 0.10,
        "warm_confirm_front_bonus": 0.4,
        "senti_hist_enabled": True,
        "senti_hist_keep_days": 10,
        "hist1d_prewarm_ttl": 600.0,
        "hist1d_prewarm_ttl_enabled": True,
        "hist1d_prewarm_until_hhmm": "10:05",
        "hist1d_core_ttl": 180.0,
        "score_recover_probe_cap_fast": 60,
        "t1_protect_enabled": True,
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
    m._is_first_board = lambda sec: True
    m._two_1m_break = lambda sec: True
    m._limit_up_within_1m = lambda sec: False
    m._vwap_follow_up = lambda sec: True
    m._l2_big_ratio = lambda sec: 0.15
    m._l2_big_ok = lambda sec: True
    m._lb_senti_gate_apply = lambda sec, action: True
    m._elastic_big_bonus_pts = lambda sec: 5.0
    m._new_themes_of = lambda sec: ["THS:新概念"]
    m._ld_theme_hit = lambda sec: None
    m._senti_stage = lambda force=False: {"flags": set()}
    m._elastic_in_strong_board = lambda sec, strong: True
    m._elastic_yizi_scan = lambda: {"B1": 2}
    m._pool = lambda: []
    m._is_elastic_eligible = lambda sec: True
    m._elastic_min_change = lambda sec: 6.0
    m.trade_open = lambda sec: True
    m._min_age = lambda: 5
    m._order_limit = lambda sec, side, mode: (9.90 if mode == "chase" else 10.90)
    m.get_trading_day = lambda: "2026-11-04"
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
        auction_confirm_log={},
        sweep_a_ld_buy={},
        senti_hist={},
        senti_stage_sell_log={},
    )
    m.last_px = lambda sec: float((m.g.spot.get(sec) or {}).get("last_px") or 0.0)
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def test_elastic_from_sweep_20cm_uses_elastic_semantics(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio, note)) or True)
    mod.g.spot["300426.SZSE"] = {
        "last_px": 9.82, "up_px": 10.80, "preclose_px": 9.00, "wavg_px": 9.60}
    mod.g.near_scan = {"300426.SZSE": {"chg": 9.1}}

    mod._try_new_theme_sweep(_ctx())

    assert len(calls) == 1
    sec, mode, ratio, note = calls[0]
    assert sec == "300426.SZSE" and mode == "chase" and ratio == 0.10
    assert "src=elastic_arb" in note and "board_limit=10.80" in note
    assert "chg=9.1%" in note
    assert "300426.SZSE" in mod.g.daily["bought_elastic_arb"]
    assert "300426.SZSE" not in mod.g.daily["bought_board"]


def test_elastic_from_sweep_warm_day_sorts_front_first(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, note)) or True)
    mod._senti_stage = lambda force=False: {"flags": {"warm_confirm_day"}}
    mod.g.spot["300426.SZSE"] = {
        "last_px": 9.82, "up_px": 10.80, "preclose_px": 9.00, "wavg_px": 9.60}
    mod.g.spot["830000.BJ"] = {
        "last_px": 9.90, "up_px": 10.80, "preclose_px": 9.00, "wavg_px": 9.60}
    mod.g.near_scan = {"300426.SZSE": {}, "830000.BJ": {}}

    mod._try_new_theme_sweep(_ctx())

    assert len(calls) == 1
    assert "stage=warm_confirm_day" in calls[0][1]


def test_elastic_20cm_near_limit_keeps_sweep_a_board(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, ratio, note)) or True)
    mod._ld_theme_hit = lambda sec: {"hard": False, "n": 0, "n_old": 0}
    mod.g.spot["300426.SZSE"] = {
        "last_px": 10.70, "up_px": 10.80, "preclose_px": 9.00, "wavg_px": 9.60}
    mod.g.near_scan = {"300426.SZSE": {"chg": 18.9}}

    mod._try_new_theme_sweep(_ctx())

    assert len(calls) == 1
    sec, mode, ratio, note = calls[0]
    assert sec == "300426.SZSE" and mode == "sweep" and ratio == 0.20
    assert "ld=0/0" in note
    assert "300426.SZSE" in mod.g.daily["bought_board"]
    assert "300426.SZSE" not in mod.g.daily["bought_elastic_arb"]


def test_elastic_arb_skip_reason_not_strong_board(mod):
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))
    mod._pool = lambda: ["300426.SZSE"]
    mod._elastic_in_strong_board = lambda sec, strong: False
    mod.g.spot["300426.SZSE"] = {
        "last_px": 9.82, "up_px": 10.80, "preclose_px": 9.00, "wavg_px": 9.60}

    mod._try_elastic_arb_buy(_ctx())

    assert any("reason=not_strong_board" in m for m in msgs)
    assert not any("reason=strong_board" in m for m in msgs)


def test_auction_confirm_log_src_and_idempotent(mod):
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))
    mod._auction_confirm_log("A", "pending_exceed", 2.5, 1.0, True, "original_0925")
    mod._auction_confirm_log("A", "pending_exceed", 2.5, 1.0, True, "original_0925")
    mod._auction_confirm_log("B", "pending_meet", -0.5, 1.0, True, "restart_rebuild")
    assert sum("src=original_0925" in m for m in msgs) == 1
    assert sum("src=restart_rebuild" in m for m in msgs) == 1
    assert "pending_exceed" in msgs[0] and "yopen=1.00%" in msgs[0]


def test_hist1d_prewarm_ttl_before_and_after_1005(mod):
    mod._hhmm = lambda: "09:58"
    assert mod._hist1d_ttl(1) == 600.0
    assert mod._hist1d_ttl(0) == 60.0
    mod._hhmm = lambda: "10:06"
    assert mod._hist1d_ttl(1) == 180.0
    assert mod._hist1d_ttl(0) == 60.0


def test_score_recover_core_priority_before_1000(mod):
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))
    mod.g.score_na_pending = {
        "LOW": {"ts": time.time() - 60, "prio": 0},
        "CORE": {"ts": time.time() - 60, "prio": 1},
    }
    mod.g.hist_na_pending = {}
    mod._lb_senti_t100_passed = lambda: False
    mod._spot_ready = lambda sec: sec == "CORE"
    mod._board_strength_info = lambda sec: (0.0, True)
    mod.score_now = lambda sec: 60.0
    mod._hist_recover_logged = lambda tag, sec: False
    mod._ma5_pending_probe = lambda: None

    mod._score_recover_probe()

    assert any("CORE" in m and "prio=1" in m for m in msgs)
    assert not any("LOW" in m for m in msgs)


def test_senti_hist_theme_zt_list_recorded(mod):
    mod._senti_theme_zt_n = lambda: (3, "光伏")
    mod._senti_theme_zt_members = lambda theme: ["A", "B", "C"]
    mod._senti_stage = lambda force=False: {"flags": {"warm_confirm_day"}}
    mod._market_red_ratio = lambda: 0.60
    mod._senti_hist_save = lambda: 0
    mod._lb_senti_state = lambda: {}
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))

    rec = mod._senti_hist_touch("auction")

    assert rec["theme_zt_list"] == ["A", "B", "C"]
    assert any("members=A,B,C" in m for m in msgs)


def test_senti_theme_zt_members_combines_dyn_and_ferment(mod):
    mod._dyn_theme_status = lambda: {"T": {"members": ["A", "B"]}}
    mod._dyn_theme_ferment = lambda: {"T": {"members": ["C"]}}
    assert mod._senti_theme_zt_members("T") == ["A", "B", "C"]


def test_t1_capture_marks_ld_hard_after_buy(mod):
    mod.g.sweep_a_ld_buy = {"A": {"day": "2026-11-04", "hard": False}}
    mod._ld_theme_hit = lambda sec: {"hard": True, "n": 1, "n_old": 1}
    mod.g.daily = mod._new_daily()
    mod.g.daily["bought"] = ["A"]
    mod.g.bought_qty = {"A": 100}
    mod.g.first_zt = {}
    mod._role_tolerance = lambda sec: {}
    mod._auction_change = lambda sec: 0.0
    mod._p2e_core_sell_check = lambda sec: (False, "")
    mod.get_stop_loss_pct = lambda sec: 0.05
    mod._p7a_check = mod._p7b_check = mod._p7d_check = lambda sec, qty: False
    mod._lb_senti_cut_hold = lambda sec: None
    mod.last_px = lambda sec: 10.0
    mod.my_cost = lambda raw, positions: 10.0
    positions = {"A": SimpleNamespace(amount=100)}

    mod._t1_protect_capture("A", "A", positions)

    rec = mod.g.t1_pending_sell["A"]
    assert "LD_HARD_AFTER_BUY" in rec["triggers"]
    assert rec.get("ld_hard_after_buy") == 1


def test_t1_consume_ld_hard_priority_sells_on_green_open(mod):
    sells = []
    mod._do_sell = lambda context, sec, qty, note, urgent=False, mode=None, cool=True: (
        sells.append((sec, qty, note, urgent)))
    mod.g.t1_pending_sell = {
        "A": {"day": "2026-11-03", "triggers": ["LD_HARD_AFTER_BUY"],
              "ld_hard_after_buy": 1, "cost": 10.0, "qty": 100},
    }
    mod.g.t1_pending_log_ts = {}
    mod._min_age = lambda: 5
    mod._norm_sec = lambda code: code
    mod._sellable = lambda raw, positions: 100
    mod._auction_change = lambda sec: -1.0
    mod._sealed_now = lambda sec: False
    mod._today_zt = lambda sec: False
    mod.last_px = lambda sec: 9.8
    mod.my_cost = lambda raw, positions: 10.0
    mod._role_tolerance = lambda sec: {}
    mod.get_stop_loss_pct = lambda sec: 0.05
    positions = {"A": SimpleNamespace(amount=100)}

    mod._t1_protect_consume(_ctx(positions))

    assert sells
    assert sells[0][0] == "A" and sells[0][1] == 100
    assert "T1_protect_ld_hard" in sells[0][2] and sells[0][3] is True
