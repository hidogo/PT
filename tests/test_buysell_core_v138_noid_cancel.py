# -*- coding: utf-8 -*-
"""v1.38 零回报无委托号排单进入封单衰减撤单闭环回归测试。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v138_noid_cancel_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "EXPECT_ORDER": False,
        "DO_ORDER": False,
        "board_queue_cancel_break_enabled": False,
        "order_no_reply_timeout": 30.0,
        "order_reconcile_interval_sec": 60.0,
        "order_inflight_heartbeat_sec": 60.0,
    })
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
    m._snl = lambda xs: ",".join(str(x) for x in (xs or []))
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-06"
    m.g = SimpleNamespace(
        zt_lianban={}, exp_file={}, spot={}, first_zt={}, pending={},
        exp_fired=set(), buy_log={}, daily={"bought": [], "sold": []},
        skip_log_ts={}, board_cancel_log=set(), last_skip_log={}, sell_skip_cnt={},
        buy_commit={}, last_no_reply_reconcile_ts=0.0, last_board_cancel_reconcile_ts=0.0,
    )
    return m


def test_query_open_order_status_backfills_empty_entrust(mod):
    mod.g.pending["001360.XSHE"] = {
        "no": "", "side": "buy", "qty": 100, "status": "SENT", "day": "2026-11-06",
    }
    mod.get_open_orders = lambda: [
        {"entrust_no": "123", "symbol": "001360.XSHE", "side": "1", "amount": 100}
    ]
    mod.get_all_orders = lambda: []

    st = mod._query_open_order_status("", sec="001360.XSHE", side="buy", qty=100, backfill=True)

    assert st == "SENT"
    assert mod.g.pending["001360.XSHE"]["no"] == "123"


def test_board_queue_cancel_backfills_ent_and_cancels_on_seal_decay(mod):
    cancelled = []
    released = []
    mod.g.pending["A"] = {
        "no": "", "side": "buy", "qty": 100, "limit": 10.0,
        "status": "SENT", "filled": 0, "ts": time.time(), "mode": "board",
        "seal_base": 1000000.0, "seal_bid_base": 10,
        "day": "2026-11-06",
    }
    mod._unique_stand = lambda sec: False
    mod.cancel_order = lambda ent: cancelled.append(ent)
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: released.append(1)

    def fake_query(ent, sec=None, side=None, qty=None, backfill=False):
        if not ent:
            mod.g.pending["A"]["no"] = "123"
            return "SENT"
        return "CANCELLED"

    mod._query_open_order_status = fake_query

    ok = mod._board_queue_cancel("A", 100000.0, 10)

    assert ok is True
    assert cancelled == ["123"]
    assert released == [1]
    assert mod.g.pending["A"]["status"] == "CANCELLED"
    assert any("[board-cancel-ok]" in x and "释放名额/承诺" in x for x in mod._logs)


def test_board_queue_cancel_no_ent_backfill_fail_keeps_cancel_pending(mod):
    cancelled = []
    released = []
    mod.g.pending["A"] = {
        "no": "", "side": "buy", "qty": 100, "limit": 10.0,
        "status": "SENT", "filled": 0, "ts": time.time(), "mode": "board",
        "seal_base": 1000000.0, "seal_bid_base": 10,
        "day": "2026-11-06",
    }
    mod._unique_stand = lambda sec: False
    mod.cancel_order = lambda ent: cancelled.append(ent)
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: released.append(1)
    mod._query_open_order_status = lambda *args, **kwargs: None

    ok = mod._board_queue_cancel("A", 100000.0, 10)

    assert ok is True
    assert cancelled == []
    assert released == []
    assert mod.g.pending["A"]["cancel_pending"] is True
    assert any("[board-cancel-noid]" in x and "cancel_pending(不释放)" in x for x in mod._logs)


def test_board_cancel_reconcile_backfills_ent_and_releases(mod):
    released = []
    mod.g.pending["A"] = {
        "no": "", "side": "buy", "qty": 100, "limit": 10.0,
        "status": "SENT", "filled": 0, "ts": time.time(), "mode": "board",
        "seal_base": 1000000.0, "seal_bid_base": 10, "cancel_pending": "True",
        "cancel_pending_ts": time.time() - 5.0, "day": "2026-11-06",
    }
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: released.append(1)

    def fake_query(ent, sec=None, side=None, qty=None, backfill=False):
        if not ent:
            mod.g.pending["A"]["no"] = "123"
            return "CANCELLED"
        return "CANCELLED"

    mod._query_open_order_status = fake_query

    assert mod._board_cancel_reconcile() == 1
    assert released == [1]
    assert mod.g.pending["A"]["status"] == "CANCELLED"
    assert "cancel_pending" not in mod.g.pending["A"]


def test_no_reply_reconcile_no_ent_emits_inflight_heartbeat(mod):
    mod.g.pending["A"] = {
        "no": "", "side": "buy", "qty": 100, "limit": 10.0,
        "status": "SENT", "ts": time.time() - 120.0,
        "day": "2026-11-06",
    }
    mod._query_open_order_status = lambda *args, **kwargs: None

    assert mod._no_reply_reconcile() == 0
    assert any("[order-inflight]" in x and "无委托号" in x and "继续等待" in x for x in mod._logs)


def test_norm_sec_920_bse_new_code(mod):
    assert mod._norm_sec("920002.XBJ") == "920002.XBJ"
    assert mod._norm_sec("920002") == "920002.XBJ"
    assert mod._is_bse("920002.XBJ") is True
