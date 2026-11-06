# -*- coding: utf-8 -*-
"""v1.46 打板灵敏度收敛：逐笔优先配额、快照弱封兜底、首帧 3s、limit-1m 优先短路。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v146_first_frame_3s_test", STRATEGY_PATH)
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
    m._hhmm = lambda: "09:35"
    m.last_px = lambda sec: float((m.g.spot.get(sec) or {}).get("last_px") or 0.0)
    m.g = SimpleNamespace(
        spot={}, first_zt={}, daily=m._new_daily(), buy_log={}, exp_file={},
        exp_fired=set(), l2_big_seeded=set(), tick_near_evt={},
        tick_buy_event_seen={}, near_scan={}, skip_log_ts={}, last_skip_log={},
        board_cancel_log=set(), first_board_fired=set(), reboard_fired=False,
    )
    return m


def _ms_before(now, secs):
    lt = time.localtime(now - secs)
    return str(int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int((now - secs) % 1 * 1000))


def test_limit_1m_first_skips_two_1m_rpc(mod):
    # L2 首帧命中时 _limit_up_within_1m 优先短路，_two_1m_break 不再消耗 m1 RPC。
    mod.g.spot["A.XSHE"] = {"last_px": 10.0, "up_px": 10.0}
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 2), "ts": time.time(), "src": "tx"}
    calls = []
    mod._two_1m_break = lambda sec: calls.append(sec) or True
    mod._below_vwap_confirm = lambda sec: False

    assert mod._core_confirm_ok("A.XSHE") is True
    assert calls == []


def test_tx_prio_fast_budget(mod):
    # 10:00 前逐笔批量/兜底走独立 fast 配额；10:00 后回落普通档。
    mod._hhmm = lambda: "09:35"
    assert mod._source_limit("tx", prio=1) == float(mod.BLS["frame_tx_prio_limit_fast"])
    assert mod._source_limit("tx", prio=0) == float(mod.BLS["frame_tx_limit_fast"])
    mod._hhmm = lambda: "10:30"
    mod._min_age = lambda: 70
    assert mod._source_limit("tx", prio=1) == float(mod.BLS["frame_tx_limit"])
    assert mod._source_limit("tx", prio=0) == float(mod.BLS["frame_tx_limit"])


def test_snap_weak_seal_falls_through_with_snap_gate(mod):
    # tx 缺失时快照兜底使用独立弱封门槛（默认 0），seal=17000/bids=6 也立即落 src=snap。
    events = []

    class FakeDh:
        def snapshot(self, secs):
            for s in secs:
                mod.g.spot[s] = {"last_px": 11.0, "up_px": 11.0, "preclose_px": 10.0,
                                 "hsTimeStamp": 123}

        def tx_zt_batch(self, secs, frame_data):
            return {}

    mod._tick_targets = lambda: ["A"]
    mod._get_ds = lambda: FakeDh()
    mod._rebuild_first_zt_tick = lambda: None
    mod._l2_big_seed_onjoin = lambda secs: None
    mod._is_one_word_open = lambda sec: False
    mod._seal_metrics = lambda sec: (17000.0, 6)
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

    mod.tick_data(SimpleNamespace(portfolio=SimpleNamespace(positions={})),
                  {"A": {"transaction": None}})

    assert mod.g.first_zt["A"]["src"] == "snap"
    assert any(e["kind"] == "firstzt" and e["sec"] == "A" for e in events)


def test_board_first_frame_fresh_3s_default(mod):
    # board_first_frame_fresh_sec 默认 3.0：首触距今 2s 放行，5s 拒绝。
    mod.g.spot["A"] = {"up_px": 10.0}
    mod.last_px = lambda sec: 10.0
    now = time.time()
    mod.g.first_zt["A"] = {"ts": now - 2.0, "ms": _ms_before(now, 2.0), "src": "tx"}
    assert mod._board_first_frame_ok("A") is True
    mod.g.first_zt["A"] = {"ts": now - 5.0, "ms": _ms_before(now, 5.0), "src": "tx"}
    assert mod._board_first_frame_ok("A") is False
