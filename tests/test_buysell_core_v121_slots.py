import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v121_slots_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "daily_max_buy": 3,
        "daily_max_board_buy": 2,
        "daily_strategy_buy_limit": {
            "exp_chase": 1,
            "ma5": 1,
            "core": 1,
            "elastic_arb": 1,
            "elastic_top": 1,
        },
        "ma5_buy_ratio": 0.10,
        "exp_order_pct": 0.10,
        "board_buy_budget_ratio": 0.20,
        "single_stock_cap": 0.30,
        "buy_lot_step": 100,
        "DO_ORDER": False,
        "EXPECT_ORDER": False,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._save_state = lambda: None
    m.g = SimpleNamespace(
        daily=m._new_daily(),
        spot={},
        skip_log_ts={},
        hist_na_pending={},
        score_na_pending={},
        ma5_pending=set(),
        last_ma5={},
        exp_file={},
        zt_lianban={},
        first_zt={},
        pending={},
        buy_log={},
        buy_commit={},
        pos_cap_skips=0,
        pos_cap_shrinks=0,
        hist1d_prewarm_prev_ok=set(),
        hist_prio_cache={},
    )
    return m


def _ctx(cash=20000.0, total=20000.0, positions=None):
    return SimpleNamespace(portfolio=SimpleNamespace(
        cash=cash,
        total_value=total,
        positions=positions or {},
    ))


def test_slot_kinds_independent_within_total(mod):
    mod._buy_slot_add("A", "core")

    assert mod._buy_slot_ok("core") is False
    assert mod._buy_slot_ok("ma5") is True
    assert mod._buy_slot_ok("elastic_arb") is True
    assert mod._buy_slot_ok("elastic_top") is True
    # v1.26 exp_chase 已删除，预期买入统一走 board；未知 kind 仍回落 bought_other 不阻塞
    assert mod._buy_slot_ok("legacy_unknown") is True


def test_total_max_3_stops_all_channels(mod):
    mod._buy_slot_add("A", "core")
    mod._buy_slot_add("B", "ma5")
    mod._buy_slot_add("C", "elastic_arb")

    assert len(mod.g.daily["bought"]) == 3
    assert mod._buy_slot_ok("core") is False
    assert mod._buy_slot_ok("ma5") is False
    assert mod._buy_slot_ok("elastic_arb") is False
    assert mod._buy_slot_ok("elastic_top") is False
    assert mod._buy_slot_ok("board") is False


def test_board_slot_has_two_quota(mod):
    mod._buy_slot_add("A", "board")
    assert mod._buy_slot_ok("board") is True
    mod._buy_slot_add("B", "board")
    assert mod._buy_slot_ok("board") is False


def test_legacy_bought_other_does_not_block_new_kinds(mod):
    mod.g.daily = {
        "bought": ["X"],
        "bought_board": [],
        "bought_other": ["X"],
        "legacy_other": ["X"],
        "sold": [],
    }

    assert mod._buy_slot_ok("ma5") is True
    assert mod._buy_slot_ok("core") is True
    assert mod._buy_slot_ok("elastic_top") is True


def test_release_only_corresponding_kind(mod):
    mod._buy_slot_add("A", "core")
    mod._buy_slot_add("B", "ma5")

    mod._buy_slot_rel("A")

    assert "A" not in mod.g.daily["bought"]
    assert "A" not in mod.g.daily["bought_core"]
    assert "A" not in mod.g.daily["bought_kind"]
    assert "B" in mod.g.daily["bought"]
    assert "B" in mod.g.daily["bought_ma5"]
    assert mod._buy_slot_ok("core") is True
    assert mod._buy_slot_ok("ma5") is False


def test_release_buy_slot_pops_exp_fired_and_kind(mod):
    mod.g.exp_fired = {"A"}
    mod._buy_slot_add("A", "core")

    mod._release_buy_slot("A")

    assert "A" not in mod.g.daily["bought"]
    assert "A" not in mod.g.daily["bought_core"]
    assert "A" not in mod.g.daily["bought_kind"]
    assert "A" not in mod.g.exp_fired


def test_ma5_pending_recover_only_once(mod):
    logs = []
    mod.log = SimpleNamespace(info=lambda msg: logs.append(msg),
                              error=lambda msg: None, warning=lambda msg: None)
    mod.g.ma5_pending = {"A"}
    mod._ma5_base4 = lambda sec: 10.0

    mod._ma5_pending_probe()
    mod._ma5_pending_probe()

    assert mod.g.ma5_pending == set()
    assert len([x for x in logs if "[ma5-recover]" in x]) == 1


def test_ma5_pending_kept_while_base4_missing(mod):
    mod.g.ma5_pending = {"A"}
    mod._ma5_base4 = lambda sec: None

    mod._ma5_pending_probe()

    assert mod.g.ma5_pending == {"A"}


def test_hist1d_prewarm_caches_ma5_without_repeat_fetch(mod):
    hist_calls = []
    ma5_calls = []
    mod._pool = lambda: ["A"]
    mod.get_positions = lambda: []
    mod._is_hist_priority = lambda sec: True
    mod._hist_1d = lambda sec, prio=0: hist_calls.append((sec, prio)) or object()
    mod._ma5_base4 = lambda sec: ma5_calls.append(sec) or 10.0

    ok = mod._hist1d_prewarm("09:25")

    assert ok == 1
    assert hist_calls == [("A", 1)]
    assert ma5_calls == ["A"]


def test_ma5_ratio_qty_10pct(mod):
    ctx = _ctx(cash=20000.0, total=20000.0)
    mod._size_cash = lambda context: float(getattr(context.portfolio, "cash", 0) or 0)
    mod._size_total = lambda context: float(getattr(context.portfolio, "total_value", 0) or 0)

    qty = mod._calc_buy_qty(ctx, "A", 10.0, float(mod.BLS["ma5_buy_ratio"]))

    assert qty == 200   # 20000×10% / (10×100)


def test_exp_chase_ratio_qty_10pct(mod):
    ctx = _ctx(cash=20000.0, total=20000.0)
    mod._size_cash = lambda context: float(getattr(context.portfolio, "cash", 0) or 0)
    mod._size_total = lambda context: float(getattr(context.portfolio, "total_value", 0) or 0)

    qty = mod._calc_buy_qty(ctx, "A", 10.0, float(mod.BLS["exp_order_pct"]))

    assert qty == 200


def test_board_ratio_qty_20pct(mod):
    ctx = _ctx(cash=20000.0, total=20000.0)
    mod._size_cash = lambda context: float(getattr(context.portfolio, "cash", 0) or 0)
    mod._size_total = lambda context: float(getattr(context.portfolio, "total_value", 0) or 0)

    qty = mod._calc_buy_qty(ctx, "A", 10.0, float(mod.BLS["board_buy_budget_ratio"]))

    assert qty == 400


def test_pos_cap_still_applies_after_qty_update(mod):
    mod._sentiment_pos_cap = lambda context, sec: 0.5
    mod._size_cash = lambda context: 10000.0
    mod._pos_value = lambda p, sec: 5000.0
    ctx = _ctx(cash=10000.0, total=15000.0, positions={"A": SimpleNamespace()})

    qty = mod._buy_pos_cap_qty(ctx, "B", 1000, 10.0)

    assert qty == 200   # 0.5×15000-5000=2500 -> 2 手
    assert mod.g.pos_cap_shrinks == 1
    assert mod.g.pos_cap_skips == 0
