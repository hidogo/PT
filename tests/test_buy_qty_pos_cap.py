import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_pos_cap_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "single_stock_cap": 0.30,
        "buy_lot_step": 100,
        "pos_cap_over_behavior": "shrink",
        "sentiment_pos_cap_enabled": True,
        "EXPECT_ORDER": False,
        "DO_ORDER": False,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m.g = SimpleNamespace(pos_cap_skips=0, pos_cap_shrinks=0, spot={}, buy_commit={},
                          cash_baseline=0.0, cash_baseline_ts=0.0)
    m._size_cash = lambda context: float(getattr(context.portfolio, "cash", 0) or 0)
    m._size_total = lambda context: float(getattr(context.portfolio, "total_value", 0) or 0)
    m.last_px = lambda sec: 0.0
    m._sn = lambda sec: sec
    return m


def test_calc_buy_qty_uses_total_asset_not_cash(mod):
    ctx = SimpleNamespace(portfolio=SimpleNamespace(cash=5000.0, total_value=20000.0, positions={}))

    qty = mod._calc_buy_qty(ctx, "A", 10.0, 0.20)

    # 总资产 20000×20%=4000；旧口径 cash×20%=1000，仅 1 手
    assert qty == 400


def test_calc_buy_qty_respects_single_stock_cap(mod):
    ctx = SimpleNamespace(portfolio=SimpleNamespace(
        cash=8000.0, total_value=20000.0,
        positions={"A": SimpleNamespace(amount=400)},
    ))

    qty = mod._calc_buy_qty(ctx, "A", 10.0, 0.20)

    # 单支上限 6000-已持 4000=2000 -> 2 手
    assert qty == 200


def test_calc_buy_qty_honors_lot_step(mod):
    mod.BLS["buy_lot_step"] = 50
    ctx = SimpleNamespace(portfolio=SimpleNamespace(cash=5000.0, total_value=20000.0, positions={}))

    qty = mod._calc_buy_qty(ctx, "A", 10.5, 0.20)

    # 4000 / (10.5×100)=3 手；步长 50 时 4000/(10.5×50)=7 步 -> 350 股
    assert qty == 350


def test_pos_cap_shrink_qty(mod):
    mod._sentiment_pos_cap = lambda context, sec: 0.5
    mod._size_cash = lambda context: 10000.0
    mod._pos_value = lambda p, sec: 5000.0
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={"A": SimpleNamespace()}))

    qty = mod._buy_pos_cap_qty(ctx, "B", 1000, 10.0)

    # total=15000, 剩余额度=0.5×15000-5000=2500 -> 2 手
    assert qty == 200
    assert mod.g.pos_cap_shrinks == 1
    assert mod.g.pos_cap_skips == 0


def test_pos_cap_shrink_below_one_lot_returns_zero(mod):
    mod._sentiment_pos_cap = lambda context, sec: 0.05
    mod._size_cash = lambda context: 10000.0
    mod._pos_value = lambda p, sec: 0.0
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))

    qty = mod._buy_pos_cap_qty(ctx, "B", 1000, 10.0)

    assert qty == 0
    assert mod.g.pos_cap_skips == 1


def test_pos_cap_skip_returns_zero(mod):
    mod.BLS["pos_cap_over_behavior"] = "skip"
    mod._sentiment_pos_cap = lambda context, sec: 0.5
    mod._size_cash = lambda context: 10000.0
    mod._pos_value = lambda p, sec: 5000.0
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={"A": SimpleNamespace()}))

    qty = mod._buy_pos_cap_qty(ctx, "B", 1000, 10.0)

    assert qty == 0
    assert mod.g.pos_cap_skips == 1
    assert mod.g.pos_cap_shrinks == 0


def test_pos_cap_within_limit_keeps_qty(mod):
    mod._sentiment_pos_cap = lambda context, sec: 0.8
    mod._size_cash = lambda context: 10000.0
    mod._pos_value = lambda p, sec: 5000.0
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={"A": SimpleNamespace()}))

    qty = mod._buy_pos_cap_qty(ctx, "B", 500, 10.0)

    assert qty == 500
    assert mod.g.pos_cap_shrinks == 0
    assert mod.g.pos_cap_skips == 0
