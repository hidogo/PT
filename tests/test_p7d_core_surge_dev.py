import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_p7d_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "p7d_sell_enabled": True,
        "p7d_limit_gap": 0.04,
        "p7d_vwap_dev_min": 3.0,
        "p7d_half_ratio": 0.5,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m.g = SimpleNamespace(
        zt_lianban={}, spot={}, first_zt={}, pending={}, exp_fired=set(),
        daily={"bought": [], "sold": []}, p7d_sold=set(),
    )
    m.last_px = lambda sec: float(m.g.spot.get(sec, {}).get("last_px") or 0.0) or None
    m._limitup_days = lambda sec: 4
    m._unique_stand = lambda sec: False
    m._sealed_now = lambda sec: False
    m._today_zt = lambda sec: False
    return m


def _spot(last=9.95, up=10.0, vwap=9.5):
    return {"last_px": last, "up_px": up, "wavg_px": vwap}


def test_p7d_fires_half_for_core_non_unique_surge(mod):
    mod.g.spot["A"] = _spot()

    note, qty = mod._p7d_check("A", 1500)

    assert qty == 700
    assert note.startswith("P7d_core_surge_dev")
    assert "dev=4.7%" in note


def test_p7d_rounds_up_small_hold_to_all(mod):
    mod.g.spot["A"] = _spot()

    note, qty = mod._p7d_check("A", 150)

    assert qty == 150
    assert note.startswith("P7d_core_surge_dev")


def test_p7d_skips_unique_leader(mod):
    mod.g.spot["A"] = _spot()
    mod._unique_stand = lambda sec: True

    assert mod._p7d_check("A", 1000) is None


def test_p7d_skips_sealed_or_today_zt(mod):
    mod.g.spot["A"] = _spot()
    mod._sealed_now = lambda sec: True
    assert mod._p7d_check("A", 1000) is None

    mod._sealed_now = lambda sec: False
    mod._today_zt = lambda sec: True
    assert mod._p7d_check("A", 1000) is None


def test_p7d_skips_non_core(mod):
    mod.g.spot["A"] = _spot()
    mod._limitup_days = lambda sec: 2

    assert mod._p7d_check("A", 1000) is None


def test_p7d_skips_missing_price_data(mod):
    mod.g.spot["A"] = {"last_px": 9.95, "up_px": 0.0, "wavg_px": 9.5}
    assert mod._p7d_check("A", 1000) is None

    mod.g.spot["A"] = {"last_px": 0.0, "up_px": 10.0, "wavg_px": 9.5}
    assert mod._p7d_check("A", 1000) is None

    mod.g.spot["A"] = {"last_px": 9.95, "up_px": 10.0, "wavg_px": 0.0}
    assert mod._p7d_check("A", 1000) is None


def test_p7d_skips_below_surge_zone(mod):
    mod.g.spot["A"] = _spot(last=9.5)
    assert mod._p7d_check("A", 1000) is None


def test_p7d_skips_insufficient_vwap_deviation(mod):
    mod.g.spot["A"] = _spot(last=9.7, up=10.0, vwap=9.5)
    assert mod._p7d_check("A", 1000) is None


def test_p7d_disabled_by_switch(mod):
    mod.g.spot["A"] = _spot()
    mod.BLS["p7d_sell_enabled"] = False

    assert mod._p7d_check("A", 1000) is None


def test_p7d_mark_persists_once(mod):
    saved = []
    mod._save_state = lambda: saved.append(1)

    mod._mark_p7("A", "p7d")

    assert "A" in mod.g.p7d_sold
    assert len(saved) == 1
