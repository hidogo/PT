"""v1.33 卖出完成数量级判定：半仓 FILLED 后剩余仓继续监控，整票 FILLED 才过滤。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v133_sell_remain_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "DO_ORDER": False,
        "EXPECT_ORDER": False,
        "sell_source_filter_sold": True,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m.g = SimpleNamespace(
        zt_lianban={}, exp_file={}, spot={}, first_zt={}, pending={},
        exp_fired=set(), buy_log={}, daily={"bought": [], "sold": []},
        skip_log_ts={}, board_cancel_log=set(), last_skip_log={}, sell_skip_cnt={},
        pos_stale_log=set(), qty_calc_last={},
    )
    return m


def test_half_sell_filled_keeps_remaining_in_sell_view(mod):
    mod.get_positions = lambda: {
        "002425.SZ": {"amount": 400, "enable_amount": 400},
    }
    # 旧版/事件表可能仍带该代码，数量级判定必须把它保留下来
    mod.g.daily["sold"] = ["002425.XSHE"]
    mod.g.pending["002425.XSHE"] = {"side": "sell", "status": "FILLED", "filled": 400, "qty": 400, "src_qty": 800}

    assert mod._sold_today_fully("002425.XSHE") is False
    assert mod._sell_order_sold_out("002425.XSHE") is False
    src = mod._sellable_source()
    assert "002425.SZ" in src
    assert mod._sellable("002425.SZ", src) == 400


def test_full_sell_filled_filters_stale_bridge_remainder(mod):
    mod.get_positions = lambda: {
        "002425.SZ": {"amount": 400, "enable_amount": 400},
    }
    mod.g.daily["sold"] = ["002425.XSHE"]
    mod.g.pending["002425.XSHE"] = {"side": "sell", "status": "FILLED", "filled": 800, "qty": 800, "src_qty": 800}

    assert mod._sold_today_fully("002425.XSHE") is True
    assert mod._sell_order_sold_out("002425.XSHE") is True
    assert mod._sellable_source() == {}


def test_legacy_filled_without_src_qty_uses_bridge_total(mod):
    mod.get_positions = lambda: {
        "002425.SZ": {"amount": 400, "enable_amount": 400},
    }
    mod.g.daily["sold"] = ["002425.XSHE"]
    mod.g.pending["002425.XSHE"] = {"side": "sell", "status": "FILLED", "filled": 400, "qty": 400}

    assert mod._sold_today_fully("002425.XSHE") is False
    assert mod._sell_order_sold_out("002425.XSHE") is False
    src = mod._sellable_source()
    assert "002425.SZ" in src


def test_legacy_filled_without_src_qty_filters_when_bridge_zero(mod):
    mod.get_positions = lambda: {
        "603533.SS": {"amount": 0, "enable_amount": 0},
    }
    mod.g.daily["sold"] = ["603533.XSHG"]
    mod.g.pending["603533.XSHG"] = {"side": "sell", "status": "FILLED", "filled": 100, "qty": 100}

    assert mod._sold_today_fully("603533.XSHG") is True
    assert mod._sellable_source() == {}


def test_legacy_filled_without_src_qty_keeps_when_bridge_unavailable(mod):
    mod.get_positions = lambda: {}
    mod.g.daily["sold"] = ["002425.XSHE"]
    mod.g.pending["002425.XSHE"] = {"side": "sell", "status": "FILLED", "filled": 400, "qty": 400}

    # 桥总量字段缺失时不能当成“已卖完”，宁可保留监控
    assert mod._sold_today_fully("002425.XSHE") is False
    assert mod._sell_order_sold_out("002425.XSHE") is False


def test_do_sell_records_src_qty_for_half_order(mod):
    mod._sellable_source = lambda: {"002425.SZ": {"amount": 800, "enable_amount": 800}}

    def fake_place(context, sec, side, qty=None, note="", mode=None, ratio=None):
        mod.g.pending[sec] = {"side": side, "qty": qty, "status": "SENT", "filled": 0}
        return True

    mod.place_order = fake_place
    mod._do_sell(None, "002425.XSHE", 400, "P6_score_half")

    assert mod.g.pending["002425.XSHE"]["src_qty"] == 800
