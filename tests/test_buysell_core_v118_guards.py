import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v118_guards_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "EXPECT_ORDER": False,
        "DO_ORDER": False,
        "exp_board_queue_gate": True,
        "exp_board_queue_max_sec": 600.0,
        "board_queue_cancel_break_enabled": True,
        "reboard_seal_min": 200000.0,
        "sell_skip_heartbeat_t1_sec": 300.0,
        "sell_source_filter_sold": True,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._snl = lambda xs: ",".join(str(x) for x in (xs or []))
    m.g = SimpleNamespace(
        zt_lianban={}, exp_file={}, spot={}, first_zt={}, pending={},
        exp_fired=set(), buy_log={}, daily={"bought": [], "sold": []},
        skip_log_ts={}, board_cancel_log=set(), last_skip_log={}, sell_skip_cnt={},
        pos_stale_log=set(), qty_calc_last={},
    )
    return m


def test_exp_board_gate_blocks_broken_and_allows_resealed(mod):
    mod.g.first_zt = {"A": {"break_cnt": 1, "break": True}}

    ok, reason = mod._exp_board_gate("A")

    assert ok is False
    assert reason == "break_open"

    mod.g.first_zt["A"]["break"] = False
    mod.g.spot["A"] = {"last_px": 10.0, "up_px": 10.0}
    mod._seal_metrics = lambda sec: (300000.0, 5)

    ok, reason = mod._exp_board_gate("A")

    assert ok is True
    assert reason == ""


def test_exp_board_gate_blocks_low_seal(mod):
    mod.g.first_zt = {"A": {"break_cnt": 1, "break": False}}
    mod.g.spot["A"] = {"last_px": 10.0, "up_px": 10.0}
    # v1.48 预期打板封单下限统一为 exp_board_seal_min=50000，低于下限应拦截
    mod._seal_metrics = lambda sec: (40000.0, 5)

    ok, reason = mod._exp_board_gate("A")

    assert ok is False
    assert reason == "seal_low"


def test_place_expected_order_board_gate_waits_without_firing(mod):
    mod.g.spot["A"] = {"last_px": 10.0, "up_px": 10.0}
    mod.g.first_zt = {"A": {"break_cnt": 1, "break": True}}
    mod._mid_board_avoid = lambda sec: False
    mod._is_st = lambda sec: False
    mod.last_px = lambda sec: 10.0
    mod._size_cash = lambda context: 100000.0
    mod._intraday_ready_detail = lambda sec: True
    mod._block_sealed_buy = lambda sec: False
    mod._exp_board_gate = lambda sec: (False, "break_open")
    mod._order_limit = lambda sec, side, mode: 10.0
    mod._log_order_limit = lambda sec, limit: None
    mod._calc_buy_qty = lambda context, sec, px, ratio: 100
    mod._buy_pos_cap_qty = lambda context, sec, qty, limit: qty
    mod._sim_mode = lambda: False
    mod._ft_state_str = lambda sec: "src:- ms:- bc:1 seal:0"
    mod._signal = lambda *args, **kwargs: None

    ok = mod.place_expected_order(SimpleNamespace(portfolio=SimpleNamespace(positions={})), "A")

    assert ok is False
    assert mod.g.exp_fired == set()


def test_place_expected_order_board_gate_allows_resealed(mod):
    mod.g.spot["A"] = {"last_px": 10.0, "up_px": 10.0}
    mod.g.first_zt = {"A": {"break_cnt": 1, "break": False, "ts": mod.time.time()}}
    mod._mid_board_avoid = lambda sec: False
    mod._is_st = lambda sec: False
    mod.last_px = lambda sec: 10.0
    mod._size_cash = lambda context: 100000.0
    mod._intraday_ready_detail = lambda sec: True
    mod._block_sealed_buy = lambda sec: False
    mod._exp_board_gate = lambda sec: (True, "")
    mod._order_limit = lambda sec, side, mode: 10.0
    mod._log_order_limit = lambda sec, limit: None
    mod._calc_buy_qty = lambda context, sec, px, ratio: 100
    mod._buy_pos_cap_qty = lambda context, sec, qty, limit: qty
    mod._sim_mode = lambda: True   # v1.48 无 L2 的测试环境按模拟/回测兼容放行
    mod._ft_state_str = lambda sec: "src:- ms:- bc:1 seal:0"
    mod._signal = lambda *args, **kwargs: None

    ok = mod.place_expected_order(SimpleNamespace(portfolio=SimpleNamespace(positions={})), "A")

    assert ok is True


def test_board_queue_cancel_cancels_on_inflight_break(mod):
    calls = []
    mod.g.pending["A"] = {
        "no": "ent-1", "side": "buy", "qty": 100, "limit": 10.0,
        "status": "SENT", "filled": 0, "ts": mod.time.time() - 5.0, "mode": "board",
        "seal_base": 1000000.0, "seal_bid_base": 10,
        "break_cnt_at_send": 0,
    }
    mod.g.first_zt = {"A": {"break_cnt": 1, "break": True, "first_seal": 1000000.0}}
    mod._unique_stand = lambda sec: False
    mod._seal_metrics = lambda sec: (900000.0, 10)
    mod._exp_board_gate = lambda sec: (False, "break_open")
    mod.cancel_order = lambda ent: calls.append(ent)
    mod._query_open_order_status = lambda *args, **kwargs: "CANCELLED"
    mod._buy_commit_rel = lambda *args, **kwargs: None
    mod._release_buy_slot = lambda *args, **kwargs: None
    logs = []
    mod.log.info = logs.append

    ok = mod._board_queue_cancel("A", 900000.0, 10)

    assert ok is True
    assert calls == ["ent-1"]
    assert mod.g.pending["A"].get("status") == "CANCELLED"
    assert mod.g.pending["A"].get("cancel_ts") is not None
    assert any("reason=break(break_open)" in x for x in logs)


def test_audit_sell_skip_t1_heartbeat_is_300s(mod):
    logs = []
    mod.log.info = logs.append
    mod.g.pending["A"] = {"side": "sell", "status": "FILLED", "filled": 100, "qty": 100}

    mod._audit_sell_skip("A", "amt0(lookup key=A field=enable_amount avail=0 total=100 t1=1)", now=1000.0)
    mod._audit_sell_skip("A", "amt0(lookup key=A field=enable_amount avail=0 total=100 t1=1)", now=1200.0)
    sell_skips = [x for x in logs if "[sell-skip]" in x]
    assert len(sell_skips) == 1
    assert "t1=1" in sell_skips[0]
    assert "300s" in sell_skips[0]

    mod._audit_sell_skip("A", "amt0(lookup key=A field=enable_amount avail=0 total=100 t1=1)", now=1300.0)
    sell_skips = [x for x in logs if "[sell-skip]" in x]
    assert len(sell_skips) == 2


def test_mid_allow_log_emitted(mod):
    logs = []
    mod.log.info = logs.append
    mod.g.zt_lianban = {"A": {"board_cnt": 3, "unique_high": 1}}
    mod.g.exp_file = {"A": {"role_detail": ""}}
    mod._dyn_theme_leader = lambda sec: False
    mod._new_themes_of = lambda sec: []
    mod._dyn_theme_ferment = lambda: {}

    allowed = mod._mid_board_avoid("A")

    assert allowed is False
    assert any("[mid-allow]" in x and "unique_high=1" in x for x in logs)


def test_qty_calc_log_emitted(mod):
    logs = []
    mod.log.info = logs.append
    mod.g.qty_calc_last = {
        "sec": "A", "price": 10.0, "cash": 10000.0, "total": 20000.0,
        "held_mv": 0.0, "cap": 6000.0, "budget": 2000.0, "lot": 1000.0, "qty": 200,
    }

    mod._qty_calc_log(None, "A", "exp-order")

    assert any("[qty-calc]" in x and "budget=2000.00" in x and "qty=200" in x for x in logs)


def test_sellable_source_filters_fully_sold(mod):
    mod.get_positions = lambda: {
        "600000.XSHG": {"amount": 100, "enable_amount": 0},
        "600001.XSHG": {"amount": 200, "enable_amount": 200},
    }
    mod.g.daily["sold"] = ["600000.XSHG"]
    mod.g.pending["600000.XSHG"] = {"side": "sell", "status": "FILLED", "filled": 100, "qty": 100, "src_qty": 100}

    src = mod._sellable_source()

    assert "600000.XSHG" not in src
    assert "600001.XSHG" in src


def test_sellable_source_keeps_partial_sell_remainder(mod):
    mod.get_positions = lambda: {
        "600000.XSHG": {"amount": 200, "enable_amount": 100},
    }
    mod.g.daily["sold"] = ["600000.XSHG"]
    mod.g.pending["600000.XSHG"] = {"side": "sell", "status": "PARTIAL", "filled": 50, "qty": 100}

    src = mod._sellable_source()

    assert "600000.XSHG" in src
