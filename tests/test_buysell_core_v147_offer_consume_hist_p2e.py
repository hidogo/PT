# -*- coding: utf-8 -*-
"""v1.47 涨停价总卖单快速消耗确认 + hist1d 当日剔除/yopen 缓存 + P2E 封死硬保护。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v147_test", STRATEGY_PATH)
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
        "weak_seal_queue_max_sec": 120.0,
        "weak_seal_extend_ratio": 3.0,
        "weak_seal_sealed_px_ratio": 0.998,
        "offer_consume_enabled": True,
        "offer_consume_ratio": 0.30,
        "offer_consume_frames": 2,
        "offer_consume_win_sec": 6.0,
        "offer_consume_zero_confirm": True,
        "p2e_sealed_hold": True,
        "p2e_sealed_px_ratio": 0.998,
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
    m._unique_stand = lambda sec: False
    m._is_hist_priority = lambda sec: False
    m._hist_1d = lambda sec, prio=0: None
    m._l2_big_ratio = lambda sec: -1.0
    m._l2_big_ok = lambda sec: False
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
    )
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def _hist_df(opens, closes, dates):
    return pd.DataFrame({"open": opens, "close": closes}, index=dates)


def test_hist_window_skips_today_row(mod):
    df = _hist_df([10.0, 10.2], [10.1, 10.3], ["2026-11-04", "2026-11-06"])
    mod._hist_1d = lambda sec, prio=0: df

    opens, closes = mod._hist_window("A")

    assert opens == [10.0]
    assert closes == [10.1]
    assert mod.g.hist_window_dates["A"]["last"] == "2026-11-06"


def test_yesterday_open_chg_cache_stable_and_audit(mod):
    df1 = _hist_df([10.0, 10.2], [10.1, 10.3], ["2026-11-03", "2026-11-04"])
    mod._hist_1d = lambda sec, prio=0: df1

    v1, h1 = mod._yesterday_open_chg("A")
    assert h1 is True
    assert abs(v1 - (10.2 / 10.1 - 1.0) * 100.0) < 1e-6

    df2 = _hist_df([9.0, 9.5], [9.1, 9.6], ["2026-11-03", "2026-11-04"])
    mod._hist_1d = lambda sec, prio=0: df2
    v2, h2 = mod._yesterday_open_chg("A")
    assert h2 is True and v2 == v1

    audit = mod._yopen_audit_str("A")
    assert "src=hist_window" in audit
    assert "hist_last=2026-11-04" in audit


def test_yesterday_open_chg_missing_not_cached(mod):
    v, h = mod._yesterday_open_chg("A")
    assert v == 0.0 and h is False
    assert "A" not in mod.g.yopen_cache

    df = _hist_df([10.0, 10.2], [10.1, 10.3], ["2026-11-03", "2026-11-04"])
    mod._hist_1d = lambda sec, prio=0: df
    v2, h2 = mod._yesterday_open_chg("A")
    assert h2 is True and v2 > 0.0


def test_offer_consume_two_frames(mod):
    seq = [100000.0, 60000.0, 30000.0]
    mod._offer_qty = lambda sec: seq.pop(0) if seq else 30000.0

    assert mod._offer_consume_ok("A") is False
    assert mod._offer_consume_ok("A") is False
    assert mod._offer_consume_ok("A") is True


def test_offer_consume_zero_confirms(mod):
    mod._offer_qty = lambda sec: 0.0
    assert mod._offer_consume_ok("A") is True


def test_offer_consume_window_reset(mod):
    mod._offer_qty = lambda sec: 100000.0
    assert mod._offer_consume_ok("A") is False

    mod.g.offer_consume["A"]["ts"] = time.time() - 7.0
    mod._offer_qty = lambda sec: 60000.0
    assert mod._offer_consume_ok("A") is False
    assert mod.g.offer_consume["A"]["frames"] == 0


def test_p2e_sealed_hold_blocks_theme_mid_sell(mod):
    mod.g.exp_file["A"] = {"side": "hold", "entry_type": "normal", "expected_status": "pending_exceed"}
    mod.g.zt_theme = {"T": {"members": {"A", "MID"}}}
    mod.g.zt_themes_of = {"A": ["T"], "MID": ["T"]}
    mod.g.zt_lianban = {"MID": {"board_cnt": 3}}
    mod._auction_change = lambda s: -5.2 if s == "MID" else -3.0
    mod._auction_benchmark = lambda s: (-0.93, True)
    mod._auction_ready = lambda s: True
    mod._confirm_expected = lambda s: (mod.PM, -3.0)
    mod._p2e_holding_reverse = lambda sec, en: (False, "")
    mod.last_px = lambda sec: 11.0
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.g.first_zt = {"A": {"break": False, "break_cnt": 0}}
    logs = []
    mod.log.info = logs.append

    hit, note, rev = mod._p2e_core_sell_check("A")

    assert hit is False and rev is True
    assert any("仍封死涨停 -> 交封单衰减保护" in x for x in logs)
    assert any("yopen=" in x and "hist_last=" in x for x in logs)


def test_board_queue_cancel_weak_seal_timeout(mod):
    calls = []
    mod.g.pending["A"] = {
        "no": "ent-1", "side": "buy", "qty": 100, "limit": 11.0,
        "status": "SENT", "filled": 0, "ts": time.time() - 200.0, "mode": "board",
        "seal_base": 30000.0, "seal_bid_base": 5, "break_cnt_at_send": 0,
    }
    mod.g.first_zt = {"A": {"break_cnt": 0, "break": False, "first_seal": 30000.0}}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.cancel_order = lambda ent: calls.append(ent)
    mod._query_open_order_status = lambda *args, **kwargs: "CANCELLED"
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: None
    logs = []
    mod.log.info = logs.append

    ok = mod._board_queue_cancel("A", 30000.0, 5)

    assert ok is True
    assert calls == ["ent-1"]
    assert mod.g.pending["A"].get("status") == "CANCELLED"
    assert any("reason=weak_seal_timeout" in x for x in logs)


def test_board_queue_cancel_weak_seal_extend(mod):
    calls = []
    mod.g.pending["A"] = {
        "no": "ent-1", "side": "buy", "qty": 100, "limit": 11.0,
        "status": "SENT", "filled": 0, "ts": time.time() - 200.0, "mode": "board",
        "seal_base": 30000.0, "seal_bid_base": 5, "break_cnt_at_send": 0,
    }
    mod.g.first_zt = {"A": {"break_cnt": 0, "break": False, "first_seal": 30000.0}}
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    mod.cancel_order = lambda ent: calls.append(ent)
    logs = []
    mod.log.info = logs.append

    ok = mod._board_queue_cancel("A", 120000.0, 10)

    assert ok is False
    assert calls == []
    assert any("弱封单续等" in x and "ratio=4.00" in x for x in logs)


def test_first_board_snap_thin_consume_confirms(mod):
    calls = []
    logs = []
    mod.log.info = logs.append
    mod._offer_consume_ok = lambda sec: True
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}
    mod.g.first_zt = {"A": {"src": "snap", "ts": time.time(), "break_cnt": 0}}
    mod._seal_metrics = lambda sec: (1000.0, 2)
    mod._order_limit = lambda sec, side, mode: 11.0
    mod._sector_chg = lambda sec: 0.1
    mod._tags = lambda sec: ["CORE"]
    mod._ft_state_str = lambda sec: "src:snap ms:- bc:0 seal:1000"
    mod._min_age = lambda: 3

    mod._try_first_board_buy(_ctx(), "A", rank_secs=["A"])

    assert len(calls) == 1 and calls[0][1] == "board"
    assert any("[firstboard-seal-thin]" in x and "offer_consume=1" in x for x in logs)


def test_first_board_snap_thin_no_consume_blocks(mod):
    calls = []
    logs = []
    mod.log.info = logs.append
    mod._offer_consume_ok = lambda sec: False
    mod.place_order = lambda context, sec, side, qty=None, note='', mode='chase', ratio=None: (
        calls.append((sec, mode, note)) or True)
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "wavg_px": 10.5}
    mod.g.first_zt = {"A": {"src": "snap", "ts": time.time(), "break_cnt": 0}}
    mod._seal_metrics = lambda sec: (1000.0, 2)
    mod._order_limit = lambda sec, side, mode: 11.0
    mod._sector_chg = lambda sec: 0.1
    mod._tags = lambda sec: ["CORE"]
    mod._ft_state_str = lambda sec: "src:snap ms:- bc:0 seal:1000"
    mod._min_age = lambda: 3

    mod._try_first_board_buy(_ctx(), "A", rank_secs=["A"])

    assert calls == []
    assert any("总卖单未快速消耗" in x for x in logs)
