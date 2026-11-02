# -*- coding: utf-8 -*-
"""v1.22 重启稳健性：日线冷缓存恢复、恢复日志去重、桥持仓审计、炸板降噪。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v122_restart_robust_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "hist1d_restart_warm_enabled": True,
        "hist1d_restart_warm_cap": 40,
        "score_recover_dedup_enabled": True,
        "firstzt_rebreak_log_sec": 30.0,
        "sell_avail_amt0_warn_only": True,
    })
    return mod


def _base_g(mod):
    return SimpleNamespace(
        daily=mod._new_daily(),
        spot={},
        exp_file={},
        zt_lianban={},
        hist_na_pending={},
        score_na_pending={},
        ma5_pending=set(),
        last_ma5={},
        hist_prio_cache={},
        hist_recover_once={},
        firstzt_log_ts={},
        bought_qty={},
        skip_log_ts={},
        pending={},
        buy_commit={},
        buy_log={},
        sold_log={},
        holdings_keys_hint=[],
        last_skip_log={},
        sell_skip_cnt={},
        sell_avail_log={},
        sell_avail_amt0_log={},
    )


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._save_state = lambda: None
    m.g = _base_g(m)
    return m


def test_restart_warm_prioritizes_pos_exp_core_and_syncs_ma5(mod):
    hist_calls = []
    ma5_calls = []
    mod.get_positions = lambda: ["600000.XSHG"]
    mod.g.exp_file = {"600001.XSHG": {"side": "buy"}}
    mod.g.zt_lianban = {"600002.XSHG": {"board_cnt": 3}, "X": {"board_cnt": 1}}
    mod._hist_1d = lambda sec, prio=0: hist_calls.append((sec, prio)) or object()
    mod._ma5_base4 = lambda sec: ma5_calls.append(sec) or 10.0

    ok = mod._hist1d_restart_warm("restart")

    assert ok == 3
    assert set(hist_calls) == {("600000.XSHG", 1), ("600001.XSHG", 1), ("600002.XSHG", 1)}
    assert sorted(ma5_calls) == ["600000.XSHG", "600001.XSHG", "600002.XSHG"]


def test_restart_warm_cap_leaves_overflow_to_pending(mod):
    mod.BLS["hist1d_restart_warm_cap"] = 2
    mod.get_positions = lambda: ["600000.XSHG"]
    mod.g.exp_file = {"600001.XSHG": {"side": "buy"}}
    mod.g.zt_lianban = {"600002.XSHG": {"board_cnt": 3}}
    hist_calls = []
    mod._hist_1d = lambda sec, prio=0: hist_calls.append(sec) or object()
    mod._ma5_base4 = lambda sec: 10.0

    ok = mod._hist1d_restart_warm("restart")

    assert ok == 2
    assert sorted(hist_calls) == ["600000.XSHG", "600001.XSHG"]
    assert "600002.XSHG" in mod.g.hist_na_pending


def test_recover_log_dedup_returns_true_on_second(mod):
    mod.get_trading_day = lambda: "2026-11-02"

    assert mod._hist_recover_logged("score", "A") is False
    assert mod._hist_recover_logged("score", "A") is True
    assert mod._hist_recover_logged("ma5", "A") is False   # 不同 tag 独立


def test_recover_log_dedup_disabled_by_param(mod):
    mod.BLS["score_recover_dedup_enabled"] = False
    mod.get_trading_day = lambda: "2026-11-02"

    assert mod._hist_recover_logged("score", "A") is False
    assert mod._hist_recover_logged("score", "A") is False


def test_score_recover_logs_once_per_day_even_if_pending_readded(mod):
    logs = []
    mod.log = SimpleNamespace(info=lambda msg: logs.append(msg),
                              error=lambda msg: None, warning=lambda msg: None)
    mod.g.hist_na_pending = {"A": time.time() - 40}
    mod.get_trading_day = lambda: "2026-11-02"
    mod._lb_senti_t100_passed = lambda: True
    mod._hist_1d = lambda sec, prio=0: object()
    mod._is_100day_high = lambda sec: True
    mod.score_now = lambda sec: 60.0
    mod._ma5_pending_probe = lambda: None

    mod._score_recover_probe()
    mod.g.hist_na_pending["A"] = time.time() - 40
    mod._score_recover_probe()

    assert len([x for x in logs if "[score-recover]" in x]) == 1
    assert "A" not in mod.g.hist_na_pending


def test_ma5_recover_logs_once_per_day_if_readded(mod):
    logs = []
    mod.log = SimpleNamespace(info=lambda msg: logs.append(msg),
                              error=lambda msg: None, warning=lambda msg: None)
    mod.g.ma5_pending = {"A"}
    mod.get_trading_day = lambda: "2026-11-02"
    mod._ma5_base4 = lambda sec: 10.0

    mod._ma5_pending_probe()
    mod.g.ma5_pending = {"A"}
    mod._ma5_pending_probe()

    assert len([x for x in logs if "[ma5-recover]" in x]) == 1
    assert mod.g.ma5_pending == set()


def test_firstzt_rebreak_log_throttled_per_stock(mod):
    assert mod._firstzt_rebreak_log("A") is True
    assert mod._firstzt_rebreak_log("A") is False
    assert mod._firstzt_rebreak_log("B") is True
    mod.g.firstzt_log_ts["A"] = time.time() - 31.0
    assert mod._firstzt_rebreak_log("A") is True


def test_break_held_ts_prefers_last_break(mod):
    now = 300.0
    ft = {"break_ts": 100.0, "last_break_ts": 200.0}
    assert mod._break_held_ts(ft, now) == 200.0

    assert mod._break_held_ts({"break_ts": 100.0}, now) == 100.0
    assert mod._break_held_ts({}, now) == now


def test_trade_response_buy_accumulates_bought_qty(mod):
    mod.g.daily = mod._new_daily()
    mod.g.pending = {}
    mod.g.bought_qty = {}
    mod.g.sold_log = {}
    mod.g.buy_commit = {}
    mod._o_get = lambda obj, *names, **kw: obj.get(names[0])
    mod._map_order_status = lambda st: ""
    mod._hold_exp_init = lambda sec: None
    mod._buy_commit_rel = lambda *a, **k: None
    mod._signal = lambda *a, **k: None
    mod._save_state = lambda: None

    trades = [
        {"stock_code": "600000.XSHG", "business_amount": 100, "entrust_bs": "1", "real_type": "0", "status": ""},
        {"stock_code": "600000.XSHG", "business_amount": 100, "entrust_bs": "1", "real_type": "0", "status": ""},
    ]
    mod.on_trade_response(SimpleNamespace(), trades)

    assert mod.g.bought_qty.get("600000.XSHG") == 200


def test_sellable_total_zero_no_backfill_and_amt0_audit(mod):
    logs = []
    mod.log = SimpleNamespace(info=lambda msg: logs.append(msg),
                              error=lambda msg: None, warning=lambda msg: None)
    mod.g.bought_qty = {"600000.XSHG": 100}
    positions = {"600000.XSHG": {"enable_amount": 0, "amount": 0}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 0
    assert key == "enable_amount"
    assert avail is True and total is True
    assert any("[pos-amt0]" in x for x in logs)
