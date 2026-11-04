# -*- coding: utf-8 -*-
"""v1.34 同帧事件派发 + 首帧 ts/tx 双基准 + 灵敏度审计。"""
import importlib.util
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v134_first_frame_events_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "DO_ORDER": False,
        "EXPECT_ORDER": False,
        "firstzt_buy_event_enabled": True,
        "board_first_frame_baseline": "ts",
        "board_first_frame_fresh_sec": 6.0,
        "tx_lag_warn_sec": 10.0,
        "tick_event_sweep_one_per_frame": True,
        "cold_secs": 0,
        "daily_max_buy": 3,
        "daily_max_board_buy": 2,
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
    m._fmt_big_ratio = lambda big: '%.1f%%' % (big * 100.0 if big and big > 0 else 0.0)
    m.get_trading_day = lambda: "2026-11-04"
    m.g = SimpleNamespace(
        spot={}, first_zt={}, daily=m._new_daily(), buy_log={}, exp_file={}, exp_fired=set(),
        l2_big_seeded=set(), tick_near_evt={}, tick_buy_event_seen={}, near_scan={},
        skip_log_ts={}, last_skip_log={}, board_cancel_log=set(), first_board_fired=set(),
        reboard_fired=False,
    )
    m.last_px = lambda sec: float((m.g.spot.get(sec) or {}).get("last_px") or 0.0)
    return m


def _ctx(positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(positions=positions or {}))


def _ms_before(now, secs):
    t = datetime.fromtimestamp(now - secs)
    return int(t.strftime('%Y%m%d%H%M%S')) * 1000 + int(((now - secs) % 1) * 1000)


def test_board_first_frame_ok_ts_and_tx_baselines(mod):
    mod.g.spot["A"] = {"last_px": 11.0, "up_px": 11.0}
    now = time.time()
    mod.g.first_zt["A"] = {"ts": now - 2.0, "ms": _ms_before(now, 2.0)}
    assert mod._board_first_frame_ok("A") is True
    assert mod._board_first_frame_ok("A", baseline="tx") is True

    mod.g.first_zt["A"]["ts"] = now - 10.0
    mod.g.first_zt["A"]["ms"] = _ms_before(now, 10.0)
    assert mod._board_first_frame_ok("A") is False
    assert mod._board_first_frame_ok("A", baseline="tx") is False

    # tx 基准缺真实首笔时回退检测帧 ts
    mod.g.first_zt["A"] = {"ts": now - 2.0}
    assert mod._board_first_frame_ok("A", baseline="tx") is True


def test_tick_buy_event_seen_day_scope(mod):
    assert mod._tick_buy_event_seen("A", "firstzt") is False
    assert mod._tick_buy_event_seen("A", "firstzt") is True
    assert mod._tick_buy_event_seen("A", "near") is False
    mod.get_trading_day = lambda: "2026-11-05"
    assert mod._tick_buy_event_seen("A", "firstzt") is False


def test_run_tick_buy_events_sorts_and_dispatch_order(mod):
    calls = []
    mod._pool_exp_priority = lambda sec: {"A": (-2.0, 1), "B": (-1.0, 2), "C": (0.0, 3)}.get(sec, (0.0, 99))
    mod._try_first_board_buy = lambda context, sec: calls.append(("first_board", sec))
    mod._try_core_buy_single = lambda context, sec: calls.append(("core", sec))
    mod._attempt_expected_buy = lambda context, sec: calls.append(("expected", sec))
    mod._try_reboard_buy = lambda context, event_sec=None: calls.append(("reboard", event_sec))
    mod._try_new_theme_sweep = lambda context, event_sec=None: calls.append(("sweep", event_sec)) or False
    mod._try_elastic_arb_buy = lambda context, event_sec=None: calls.append(("elastic", event_sec)) or False

    events = [
        {"kind": "firstzt", "sec": "B"},
        {"kind": "near", "sec": "C"},
        {"kind": "firstzt", "sec": "A"},
        {"kind": "reboard", "sec": "D"},
    ]
    mod._run_tick_buy_events(_ctx(), events)

    assert calls[0] == ("first_board", "A")
    assert calls[1] == ("core", "A")
    assert calls[2] == ("expected", "A")
    assert calls[3] == ("first_board", "B")
    assert ("reboard", "D") in calls
    assert ("sweep", "C") in calls
    assert ("elastic", "C") in calls


def test_run_tick_buy_events_stops_same_stock_after_placement(mod):
    calls = []

    def first_board(context, sec):
        calls.append(("first_board", sec))
        mod.g.daily["bought"].append(sec)
        mod.g.daily["bought_board"].append(sec)

    mod._pool_exp_priority = lambda sec: (0.0, 1)
    mod._try_first_board_buy = first_board
    mod._try_core_buy_single = lambda context, sec: calls.append(("core", sec))
    mod._attempt_expected_buy = lambda context, sec: calls.append(("expected", sec))
    mod._try_new_theme_sweep = lambda context, event_sec=None: calls.append(("sweep", event_sec)) or False
    mod._try_elastic_arb_buy = lambda context, event_sec=None: calls.append(("elastic", event_sec)) or False

    mod._run_tick_buy_events(_ctx(), [{"kind": "firstzt", "sec": "A"}])

    assert calls == [("first_board", "A")]


def test_run_tick_buy_events_sweep_one_per_frame(mod):
    calls = []
    mod._pool_exp_priority = lambda sec: (0.0, 1)
    mod._try_new_theme_sweep = lambda context, event_sec=None: (calls.append(("sweep", event_sec)) or True)
    mod._try_elastic_arb_buy = lambda context, event_sec=None: (calls.append(("elastic", event_sec)) or True)

    mod._run_tick_buy_events(_ctx(), [{"kind": "near", "sec": "C"}])

    assert calls == [("sweep", "C")]


def test_tx_lag_warn_logs_when_provider_late(mod):
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))
    now = time.time()
    ft = {"ts": now, "ms": _ms_before(now, 12.0), "src": "tx"}
    mod._tx_lag_warn("A", ft)
    assert any("[tx-lag]" in m and "feed_lag=12.0" in m and "src=tx" in m for m in msgs)


def test_buy_ff_log_audit(mod):
    msgs = []
    mod.log.info = lambda msg: msgs.append(str(msg))
    mod.g.first_zt["A"] = {"ts": time.time(), "src": "tx", "break_cnt": 0}
    mod._buy_ff_log("A", "expected", "ok")
    assert any("[buy-ff] A path=expected baseline=ts" in m and "gate=ok" in m for m in msgs)


def test_tick_data_collects_firstzt_and_near_events(mod):
    events = []

    class FakeDh:
        def snapshot(self, secs):
            for s in secs:
                mod.g.spot[s] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0, "hsTimeStamp": 123}

        def tx_zt_batch(self, secs, frame_data):
            return {"A": 20261104093001000}

    mod._tick_targets = lambda: ["A"]
    mod._get_ds = lambda: FakeDh()
    mod._rebuild_first_zt_tick = lambda: None
    mod._l2_big_seed_onjoin = lambda secs: None
    mod._is_one_word_open = lambda sec: False
    mod._seal_metrics = lambda sec: (1000.0, 2)
    mod._seal_book_ok = lambda sec: True
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda s: 10000.0
    mod._l2_big_seed = lambda secs: None
    mod._log_l2_big_seed_summary = lambda sec: None
    mod._tx_lag_warn = lambda sec, ft=None: None
    mod._update_seal_low_state = lambda *a, **k: None
    mod._board_queue_cancel = lambda sec, seal, bids: None
    mod._gear_batch_health = lambda: (False, 1, 0, 0.0)
    mod._reset_seal_low_confirm_on_batch_bad = lambda: None
    mod._t1_protect_consume = lambda context: None
    mod.tick_sell_manager = lambda context: None
    mod._try_reboard_buy = lambda context, event_sec=None: None
    mod._try_expected_buys = lambda context: None
    mod._try_elastic_arb_buy = lambda context, event_sec=None: None
    mod._try_elastic_top_buy = lambda context: None
    mod._try_dyn_unq = lambda context: None
    mod._try_new_theme_sweep = lambda context, event_sec=None: None
    mod._budget_log = lambda: None
    mod._run_tick_buy_events = lambda context, ev: events.extend(ev)
    mod._set_now = lambda context: None

    mod.tick_data(_ctx(), {"A": {"transaction": None}})

    kinds = sorted(e["kind"] for e in events)
    assert kinds == ["firstzt", "near"]
    assert mod.g.first_zt["A"]["src"] == "tx"
    assert "A" in mod.g.tick_near_evt
