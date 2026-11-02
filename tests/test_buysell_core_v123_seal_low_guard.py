# -*- coding: utf-8 -*-
"""v1.23 SEAL_LOW 稳健性：L2 批量空档不误卖、两帧确认、封死恢复清除。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v123_seal_low_guard_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "seal_low_confirm_sec": 6.0,
        "seal_low_batch_invalid_ratio": 0.3,
        "seal_low_batch_invalid_min": 5,
    })
    return mod


def _base_g(mod):
    return SimpleNamespace(
        first_zt={},
        spot={},
        seal_sold=set(),
        sold_log={},
        seal_batch_unhealthy=False,
        gear_invalid_cnt=0,
        gear_total_cnt=0,
        skip_log_ts={},
        last_skip_log={},
    )


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._mark_sold_event = lambda sec, tag: None
    m._skip_log = lambda tag, sec, reason, msg, throttle_sec=None: None
    m._hold_exp_init = lambda sec: None
    m._sell_inflight = lambda sec: False
    m._sellable = lambda raw, positions: 400
    m._sellable_source = lambda: {"000525.XSHE": {}}
    m._role_tolerance = lambda sec: {"green_tol": 1.0, "stop_adj": 1.0}
    m._p2e_core_sell_check = lambda sec: (False, "")
    m.my_cost = lambda raw, positions: 4.0
    m.last_px = lambda sec: 4.94
    m._auction_change = lambda sec: 10.0
    m._is_st = lambda sec: False
    m.g = _base_g(m)
    return m


def _seed_ft(mod, seal_low=False, confirm_ts=None):
    mod.g.first_zt["000525.XSHE"] = {
        "first_seal": 27813212.0,
        "seal_low": seal_low,
        "seal_low_confirm_ts": confirm_ts or 0.0,
        "break": False,
        "break_cnt": 0,
    }


def test_seal_book_ok_rejects_empty_batch_book(mod):
    mod._gear = lambda sec: {}
    assert mod._seal_book_ok("000525.XSHE") is False


def test_seal_book_ok_accepts_bid_grp_present(mod):
    mod._gear = lambda sec: {"bid_grp": {1: [4.94, 0, 0]}}
    assert mod._seal_book_ok("000525.XSHE") is True


def test_seal_low_single_frame_waits_for_confirm(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time())
    calls = []
    mod._do_sell = lambda *a, **k: calls.append(a)
    mod.tick_sell_manager(object())
    assert calls == []


def test_seal_low_confirmed_two_frames_sells(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time() - 6.5)
    calls = []
    mod._do_sell = lambda *a, **k: calls.append((a, k))
    mod.tick_sell_manager(object())
    assert calls and calls[0][0][2] == 400


def test_seal_low_fast_sells_on_first_frame(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time())
    mod.g.first_zt["000525.XSHE"]["seal_low_fast"] = True
    calls = []
    mod._do_sell = lambda *a, **k: calls.append((a, k))
    mod.tick_sell_manager(object())
    assert calls and calls[0][0][2] == 400


def test_seal_low_batch_unhealthy_skips_even_if_confirmed(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time() - 10.0)
    mod.g.seal_batch_unhealthy = True
    calls = []
    mod._do_sell = lambda *a, **k: calls.append(a)
    mod.tick_sell_manager(object())
    assert calls == []


def test_batch_unhealthy_resets_confirm_timer(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time() - 10.0)
    mod.g.gear_total_cnt = 20
    mod.g.gear_invalid_cnt = 12
    unhealthy, total, invalid, ratio = mod._gear_batch_health()
    assert unhealthy is True
    assert total == 20 and invalid == 12
    assert ratio >= 0.3
    mod._reset_seal_low_confirm_on_batch_bad()
    ft = mod.g.first_zt["000525.XSHE"]
    assert ft["seal_low_confirm_ts"] > time.time() - 1.0


def test_gear_batch_health_below_threshold(mod):
    mod.g.gear_total_cnt = 20
    mod.g.gear_invalid_cnt = 2
    unhealthy, total, invalid, ratio = mod._gear_batch_health()
    assert unhealthy is False
    assert ratio == 0.1


def test_seal_low_recovery_clears_flag_when_at_limit(mod):
    _seed_ft(mod, seal_low=True, confirm_ts=time.time())
    ft = mod.g.first_zt["000525.XSHE"]
    ft["break"] = False
    mod._update_seal_low_state(ft, "000525.XSHE", 4.94, 4.94, 0.0, 0, False, ft["first_seal"],
                               float(mod.BLS.get("seal_fail_ratio", 0.333)))
    assert ft["seal_low"] is False
    assert "seal_low_confirm_ts" not in ft


def test_update_seal_low_sets_flag_only_with_valid_book(mod):
    ft = {"seal_low": False, "break": False}
    mod._update_seal_low_state(ft, "000525.XSHE", 4.94, 4.94, 0.0, 0, False, 27813212.0, 0.333)
    assert ft.get("seal_low") is False
    assert "seal_low_confirm_ts" not in ft

    mod._update_seal_low_state(ft, "000525.XSHE", 4.94, 4.94, 1000.0, 0, True, 27813212.0, 0.333)
    assert ft.get("seal_low") is True
    assert "seal_low_confirm_ts" in ft


def test_update_seal_low_fast_flag_when_collapse_below_fast_ratio(mod):
    ft = {"seal_low": False, "break": False}
    mod._update_seal_low_state(ft, "000525.XSHE", 4.94, 4.94, 3000000.0, 0, True, 27813212.0, 0.333,
                               float(mod.BLS.get("seal_low_fast_ratio", 0.15)))
    assert ft.get("seal_low_fast") is True
    assert "seal_low_fast_ts" in ft
