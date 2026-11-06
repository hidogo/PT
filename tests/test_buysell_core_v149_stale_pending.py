# -*- coding: utf-8 -*-
"""v1.49 跨日死单：收盘收口、日切隔离、次日终态复核/无匹配释放回归测试。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v149_stale_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "pending_stale_release_on_lost": True,
        "pending_stale_heartbeat_sec": 300.0,
        "order_reconcile_interval_sec": 60.0,
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
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-07"
    m._skip_log = lambda *a, **k: None
    m.g = SimpleNamespace(
        pending={},
        pending_stale={},
        pending_stale_reconcile_day=None,
        buy_commit={},
        daily=m._new_daily(),
        exp_fired=set(),
        first_zt={},
        skip_log_ts={},
        last_skip_log={},
        sell_skip_cnt={},
        last_no_reply_reconcile_ts=0.0,
        last_board_cancel_reconcile_ts=0.0,
    )
    return m


def _add_slot(mod, sec):
    mod.g.daily["bought"].append(sec)
    mod.g.daily["bought_board"].append(sec)


def _buy_pending(no="", status="SENT", day="2026-11-06", extra=None):
    pp = {
        "no": no, "side": "buy", "qty": 100, "limit": 10.0,
        "status": status, "filled": 0, "ts": 1000.0, "mode": "board",
        "day": day,
    }
    if extra:
        pp.update(extra)
    return pp


def test_pending_day_backfill_fills_missing_day(mod):
    mod.g.pending["A"] = _buy_pending()
    mod.g.pending["A"].pop("day", None)
    mod.g.pending["B"] = _buy_pending(day="2026-11-06")

    mod._pending_day_backfill()

    assert mod.g.pending["A"]["day"] == "2026-11-07"
    assert mod.g.pending["B"]["day"] == "2026-11-06"


def test_quarantine_stale_pending_moves_old_buy_only(mod):
    mod.g.pending["A"] = _buy_pending(day="2026-11-06")
    mod.g.pending["B"] = _buy_pending(day="2026-11-07")
    mod.g.pending["S"] = dict(_buy_pending(day="2026-11-06"), side="sell")

    assert mod._quarantine_stale_pending() == 1
    assert "A" in mod.g.pending_stale
    assert mod.g.pending_stale["A"]["day_entered"] == "2026-11-07"
    assert "A" not in mod.g.pending
    assert "B" in mod.g.pending
    assert "S" in mod.g.pending


def test_close_order_sweep_releases_quarantines_but_not_cancel(mod):
    mod.g.pending["A"] = _buy_pending(day="2026-11-07", status="SENT")
    mod.g.pending["B"] = _buy_pending(
        day="2026-11-07", status="SENT", extra={"cancel_pending": "True"})
    mod.g.pending["C"] = _buy_pending(day="2026-11-07", status="FILLED", no="c-1")
    mod.g.buy_commit = {"A": 1000.0, "B": 1000.0}
    _add_slot(mod, "A")
    cancel_calls = []
    mod.cancel_order = lambda ent: cancel_calls.append(ent)

    def fake_query(ent, sec=None, side=None, qty=None, backfill=False):
        if sec == "A":
            return "CANCELLED"
        return ""

    mod._query_open_order_status = fake_query

    assert mod._close_order_sweep() == 2
    assert "A" not in mod.g.pending
    assert "A" not in mod.g.daily["bought"]
    assert "A" not in mod.g.daily["bought_board"]
    assert "A" not in mod.g.buy_commit
    assert "B" in mod.g.pending_stale
    assert "B" not in mod.g.pending
    assert "C" in mod.g.pending
    assert cancel_calls == []


def test_stale_reconcile_filled_keeps_slot(mod):
    mod.g.pending_stale["A"] = _buy_pending()
    mod.g.buy_commit = {"A": 1000.0}
    _add_slot(mod, "A")
    mod._query_open_order_status = lambda *args, **kwargs: "FILLED"
    mod.get_all_orders = lambda: []
    mod.get_positions = lambda: {}

    assert mod._stale_pending_reconcile() == 1
    assert mod.g.pending_stale == {}
    assert mod.g.buy_commit == {}
    assert mod.g.daily["bought"] == ["A"]


def test_stale_reconcile_has_pos_treated_filled(mod):
    mod.g.pending_stale["A"] = _buy_pending()
    mod.g.buy_commit = {"A": 1000.0}
    _add_slot(mod, "A")
    mod._query_open_order_status = lambda *args, **kwargs: ""
    mod.get_all_orders = lambda: []
    mod.get_positions = lambda: {"A": {"amount": 100}}

    assert mod._stale_pending_reconcile() == 1
    assert mod.g.pending_stale == {}
    assert mod.g.buy_commit == {}
    assert mod.g.daily["bought"] == ["A"]


def test_stale_reconcile_lost_nopos_releases(mod):
    mod.g.pending_stale["A"] = _buy_pending()
    mod.g.buy_commit = {"A": 1000.0}
    _add_slot(mod, "A")
    mod._query_open_order_status = lambda *args, **kwargs: ""
    mod.get_all_orders = lambda: []
    mod.get_positions = lambda: {}

    assert mod._stale_pending_reconcile() == 1
    assert mod.g.pending_stale == {}
    assert mod.g.buy_commit == {}
    assert mod.g.daily["bought"] == []
    assert any("[stale-pending-release]" in x for x in mod._logs)


def test_stale_reconcile_release_param_off_keeps_isolated(mod):
    mod.BLS["pending_stale_release_on_lost"] = False
    mod.g.pending_stale["A"] = _buy_pending()
    mod._query_open_order_status = lambda *args, **kwargs: ""
    mod.get_all_orders = lambda: []
    mod.get_positions = lambda: {}
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)

    assert mod._stale_pending_reconcile() == 0
    assert "A" in mod.g.pending_stale
    assert any("[stale-pending]" in x and "保持隔离" in x for x in logs)


def test_stale_reconcile_inflight_keeps_isolated_heartbeat(mod):
    mod.g.pending_stale["A"] = _buy_pending()
    mod._query_open_order_status = lambda *args, **kwargs: "SENT"
    mod.get_all_orders = lambda: []
    mod.get_positions = lambda: {}
    logs = []
    mod._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: logs.append(msg)

    assert mod._stale_pending_reconcile() == 0
    assert "A" in mod.g.pending_stale
    assert mod.g.pending_stale_reconcile_day == "2026-11-07"
    assert any("[stale-pending]" in x and "保持隔离" in x for x in logs)
