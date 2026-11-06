# -*- coding: utf-8 -*-
"""v1.48 全局修复：yopen 权威迟到刷新/封单链路统一/L2 缺失不静默放行/普适封死不核卖。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v148_test", STRATEGY_PATH)
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
        "board_rank_enabled": False,
        "first_board_minute": 10,
        "first_board_seal_min": 50000.0,
        "reboard_seal_min": 50000.0,
        "exp_board_seal_min": 50000.0,
        "weak_seal_queue_max_sec": 120.0,
        "weak_seal_extend_ratio": 3.0,
        "weak_seal_extend_max": 1,
        "weak_seal_sealed_px_ratio": 0.998,
        "offer_consume_enabled": True,
        "offer_consume_ratio": 0.30,
        "offer_consume_frames": 2,
        "offer_consume_win_sec": 6.0,
        "offer_consume_zero_confirm": True,
        "p2e_sealed_hold": True,
        "sealed_sell_hold": True,
        "sealed_sell_px_ratio": 0.998,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-06"
    m._min_age = lambda: 5
    m._hhmm = lambda: "09:35"
    m._is_st = lambda sec: False
    m._is_one_word_open = lambda sec: False
    m._block_sealed_buy = lambda sec: False
    m._mid_board_avoid = lambda sec: False
    m._ferment_front_gate = lambda sec: True
    m._lb_senti_gate_apply = lambda sec, action: True
    m._is_first_board = lambda sec: True
    m._board_top_gainer = lambda sec: True
    m._board_first_zt = lambda sec: True
    m._board_rank_top3 = lambda sec, secs: True
    m._unique_stand = lambda sec: False
    m._is_hist_priority = lambda sec: False
    m._hist_1d = lambda sec, prio=0: None
    m._l2_big_ratio = lambda sec: -1.0
    m._l2_big_ok = lambda sec: False
    m._limitup_days = lambda sec: 1
    m._buy_ff_log = lambda *a, **k: None
    m._board_first_frame_ok = lambda sec: True
    m._buy_slot_ok = lambda kind: True
    m._buy_slot_add = lambda sec, kind: None
    m._order_limit = lambda sec, side, mode: 11.0
    m.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: True
    m._seal_metrics = lambda sec: (50000.0, 5)
    m._seal_book_ok = lambda sec: True
    m._sim_mode = lambda: False
    m._skip_log = lambda *a, **k: None
    m.g = SimpleNamespace(
        daily=m._new_daily(),
        spot={},
        near_scan={},
        pool_static=[],
        watch=[],
        exp={},
        exp_file={},
        first_zt={},
        buy_log={},
        vwap_track={},
        skip_log_ts={},
        last_skip_log={},
        sell_skip_cnt={},
        pending={},
        board_cancel_log=set(),
        yopen_cache={},
        hist_window_dates={},
        offer_consume={},
        p2e_reverse_log={},
        zt_lianban={},
        zt_theme={},
        zt_themes_of={},
        auction_c={},
        sold_log={},
        exp_day=None,
        holdings_keys_hint=[],
        first_board_fired=set(),
        reboard_fired=False,
    )
    return m


def _hist_df(opens, closes, dates):
    return pd.DataFrame({"open": opens, "close": closes}, index=dates)


def test_yopen_file_late_refreshes_cache(mod):
    df1 = _hist_df([10.0, 10.2], [10.1, 10.3], ["2026-11-04", "2026-11-05"])
    mod._hist_1d = lambda sec, prio=0: df1

    v1, h1 = mod._yesterday_open_chg("A")
    assert h1 is True and v1 > 0.0
    assert mod.g.yopen_cache["A"]["src"] == "hist_window"

    mod.g.exp_file["A"] = {"has_yesterday_open": True, "yesterday_open_pct": 1.5}
    v2, h2 = mod._yesterday_open_chg("A")
    assert h2 is True and abs(v2 - 1.5) < 1e-6
    assert mod.g.yopen_cache["A"]["src"] == "exp_file"


def test_yopen_synth_entry_not_authoritative(mod):
    df1 = _hist_df([10.0, 10.2], [10.1, 10.3], ["2026-11-04", "2026-11-05"])
    mod._hist_1d = lambda sec, prio=0: df1
    mod._yesterday_open_chg("A")

    mod.g.exp_file["A"] = {"has_yesterday_open": True, "yesterday_open_pct": 9.0, "_src": "zt_pool"}
    v2, h2 = mod._yesterday_open_chg("A")
    assert h2 is True and v2 < 9.0
    assert mod.g.yopen_cache["A"]["src"] == "hist_window"


def test_maybe_roll_day_resets_v147_state(mod):
    mod.g.exp_day = "2026-11-05"
    mod.g.yopen_cache["A"] = {"day": "2026-11-06", "val": 1.0, "has": True, "src": "exp_file"}
    mod.g.hist_window_dates["A"] = {"day": "2026-11-06", "last": "2026-11-06"}
    mod.g.offer_consume["A"] = {"day": "2026-11-06", "qty": 1.0, "ts": time.time(), "frames": 2}

    assert mod._maybe_roll_day() is True
    assert mod.g.yopen_cache == {}
    assert mod.g.hist_window_dates == {}
    assert mod.g.offer_consume == {}
    assert mod.g.p2e_reverse_log == {}


def test_exp_board_gate_offer_consume_ok(mod):
    mod.g.first_zt["A"] = {"break_cnt": 1, "break": False}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod._seal_metrics = lambda sec: (30000.0, 5)
    mod._offer_consume_ok = lambda sec: True

    ok, reason = mod._exp_board_gate("A")
    assert ok is True and reason == ""


def test_exp_board_gate_tx_exempt(mod):
    mod.g.first_zt["A"] = {"break_cnt": 1, "break": False, "src": "tx"}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod._seal_metrics = lambda sec: (30000.0, 5)

    ok, reason = mod._exp_board_gate("A")
    assert ok is True and reason == ""


def test_exp_board_gate_seal_na_live(mod):
    mod.g.first_zt["A"] = {"break_cnt": 1, "break": False}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod._seal_metrics = lambda sec: (0.0, 0)
    mod._seal_book_ok = lambda sec: False

    ok, reason = mod._exp_board_gate("A")
    assert ok is False and reason == "seal_na"


def test_reboard_seal_thin_consume_confirms(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod.g.first_zt["A"] = {"break_cnt": 1, "break": False, "reboard_ts": time.time()}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod._seal_metrics = lambda sec: (30000.0, 5)
    mod._offer_consume_ok = lambda sec: True

    mod._try_reboard_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})), event_sec="A")

    assert len(calls) == 1 and calls[0][1] == "board"
    assert "reboard_buy" in calls[0][2]


def test_reboard_seal_thin_no_consume_blocks(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod.g.first_zt["A"] = {"break_cnt": 1, "break": False, "reboard_ts": time.time()}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod._seal_metrics = lambda sec: (30000.0, 5)
    mod._offer_consume_ok = lambda sec: False
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)

    mod._try_reboard_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})), event_sec="A")

    assert calls == []
    assert any("封单不足" in x for x in logs)


def test_first_board_seal_na_live_blocks(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod._seal_metrics = lambda sec: (0.0, 0)
    mod._seal_book_ok = lambda sec: False
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)
    mod.g.first_zt["A"] = {"src": "snap", "ts": time.time(), "break_cnt": 0}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}

    mod._try_first_board_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})), "A", rank_secs=["A"])

    assert calls == []
    assert any("firstboard-seal-na" in x for x in logs)


def test_first_board_seal_na_sim_allows(mod):
    calls = []
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod._seal_metrics = lambda sec: (0.0, 0)
    mod._seal_book_ok = lambda sec: False
    mod._sim_mode = lambda: True
    mod.g.first_zt["A"] = {"src": "snap", "ts": time.time(), "break_cnt": 0}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}

    mod._try_first_board_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})), "A", rank_secs=["A"])

    assert len(calls) == 1 and calls[0][1] == "board"


def test_board_queue_cancel_weak_seal_extend_max(mod):
    cancel_calls = []
    mod.g.pending["A"] = {
        "no": "ent-1", "side": "buy", "qty": 100, "limit": 11.0,
        "status": "SENT", "filled": 0, "ts": time.time() - 200.0, "mode": "board",
        "seal_base": 30000.0, "seal_bid_base": 5, "break_cnt_at_send": 0,
    }
    mod.g.first_zt = {"A": {"break_cnt": 0, "break": False, "first_seal": 30000.0}}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.cancel_order = lambda ent: cancel_calls.append(ent)
    mod._query_open_order_status = lambda *args, **kwargs: "CANCELLED"
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: None

    assert mod._board_queue_cancel("A", 120000.0, 10) is False
    assert mod.g.pending["A"].get("weak_seal_extend_cnt") == 1
    assert mod._board_queue_cancel("A", 120000.0, 10) is True
    assert mod.g.pending["A"].get("status") == "CANCELLED"


def test_sealed_sell_hold_blocks_hard_sell(mod):
    mod._sealed_sell_hold = lambda sec: True
    sells = []
    mod._do_sell = lambda *a, **k: sells.append(a)
    mod._sellable_source = lambda: {"A": SimpleNamespace()}
    mod._sellable = lambda raw, positions: 100
    mod.last_px = lambda sec: 11.0
    mod._role_tolerance = lambda sec: {"green_tol": 1.0, "stop_adj": 1.0,
                                       "score_clear_adj": 1.0, "score_half_adj": 1.0}
    mod._auction_change = lambda sec: -3.0
    mod._hold_exp_init = lambda sec: None
    mod._sell_inflight = lambda sec: False
    mod._t1_protect_capture = lambda *a, **k: None
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)

    mod.sell_manager(SimpleNamespace(portfolio=SimpleNamespace(positions={"A": SimpleNamespace()})))

    assert sells == []
    assert any("[sell-sealed-hold]" in x for x in logs)


def test_tick_break_sell_not_blocked_by_hold(mod):
    mod._sealed_sell_hold = lambda sec: False
    sells = []
    mod._do_sell = lambda context, sec, qty, note, **kwargs: sells.append((sec, qty, note))
    mod._sellable_source = lambda: {"A": SimpleNamespace()}
    mod._sellable = lambda raw, positions: 100
    mod.last_px = lambda sec: 10.5
    mod._hold_exp_init = lambda sec: None
    mod._sell_inflight = lambda sec: False
    mod._t1_protect_capture = lambda *a, **k: None
    mod._break_held_ts = lambda ft, now=None: 0.0
    mod._mark_sold_event = lambda sec, kind: None
    mod._save_state = lambda: None
    mod.g.first_zt["A"] = {"break": True, "break_cnt": 1}

    mod.tick_sell_manager(SimpleNamespace(portfolio=SimpleNamespace(positions={"A": SimpleNamespace()})))

    assert len(sells) == 1
    assert "TICK_break_sell" in sells[0][2]


def test_sealed_sell_hold_helper_flags(mod):
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.g.first_zt["A"] = {"break": False}
    assert mod._sealed_sell_hold("A") is True

    mod.g.first_zt["A"]["break"] = True
    assert mod._sealed_sell_hold("A") is False

    mod.g.first_zt["A"]["break"] = False
    mod.g.spot["A"]["last_px"] = 10.5
    assert mod._sealed_sell_hold("A") is False


def test_offer_qty_limit_up_levels_only(mod):
    mod.g.spot["A"] = {"up_px": 11.0}
    mod._gear = lambda sec: {
        "offer_grp": {
            1: [11.0, 50000.0, 5],
            2: [10.9, 100000.0, 10],
        }
    }
    assert mod._offer_qty("A") == 50000.0

    mod._gear = lambda sec: {"offer_grp": {}}
    mod.g.spot["A"]["total_offerqty"] = 30000.0
    assert mod._offer_qty("A") == 30000.0
