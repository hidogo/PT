import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v120_fixes_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "sell_avail_backfill_enabled": True,
        "sell_avail_t1_strict": True,
        "frame_hist1d_prio_limit_fast": 40,
        "frame_hist1d_prio_limit": 12,
        "hist1d_core_ttl": 180.0,
        "p6_two_frame_enabled": True,
        "p6_confirm_frames": 2,
        "p6_confirm_win_sec": 30.0,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._sn = lambda sec: sec
    m._save_state = lambda: None
    m.g = SimpleNamespace(
        daily={"bought": [], "bought_board": [], "bought_other": [], "sold": []},
        spot={}, p6_weak={}, sell_avail_log={}, skip_log_ts={},
        hist_na_pending={}, score_na_pending={}, pos_stale_log=set(),
        last_skip_log={}, sell_skip_cnt={}, holdings_keys_hint=[],
        zt_lianban={}, exp_file={}, first_zt={}, pending={},
    )
    return m


def test_sellable_backfills_prev_day_zero_enable(mod):
    positions = {"600000.XSHG": {"amount": 200, "enable_amount": 0}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 200
    assert key == "enable_backfill"
    assert avail is True and total is True


def test_sellable_keeps_t1_zero_for_today_bought(mod):
    mod.g.daily["bought"] = ["600000.XSHG"]
    positions = {"600000.XSHG": {"amount": 200, "enable_amount": 0}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 0
    assert key == "enable_amount"


def test_sellable_t0_switch_backfills_today_bought(mod):
    mod.BLS["sell_avail_t1_strict"] = False
    mod.g.daily["bought"] = ["600000.XSHG"]
    positions = {"600000.XSHG": {"amount": 200, "enable_amount": 0}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 200
    assert key == "enable_backfill"


def test_sellable_keeps_real_avail(mod):
    positions = {"600000.XSHG": {"amount": 200, "enable_amount": 100}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 100
    assert key == "enable_amount"


def test_sellable_no_total_no_backfill(mod):
    positions = {"600000.XSHG": {"enable_amount": 0}}

    qty, key, avail, total = mod._sellable_backfill_detail("600000.XSHG", positions)

    assert qty == 0
    assert avail is True and total is False


def test_source_limit_hist1d_prio_fast_before_1000(mod):
    mod._min_age = lambda: 5

    assert mod._source_limit("hist1d", prio=1) == 40


def test_source_limit_hist1d_prio_normal_after_1000(mod):
    mod._min_age = lambda: 35

    assert mod._source_limit("hist1d", prio=1) == 12


def test_hist1d_core_ttl_amplified(mod):
    seen = []

    def cached(source, sec, ttl, fetch, budget=None, stale_ok=False, prio=0, single=False):
        seen.append((ttl, prio))
        return object()

    mod._get_ds = lambda: SimpleNamespace(cached=cached)
    mod._hist_1d("A", prio=1)
    mod._hist_1d("A", prio=0)

    assert seen == [(180.0, 1), (60.0, 0)]


def test_score_recover_probe_hist_uses_prio1(mod):
    calls = []
    mod.g.hist_na_pending = {"A": time.time() - 40}
    mod._lb_senti_t100_passed = lambda: True
    mod._hist_1d = lambda sec, prio=0: calls.append(prio) or object()
    mod._is_100day_high = lambda sec: True
    mod.score_now = lambda sec: 60.0

    mod._score_recover_probe()

    assert calls == [1]
    assert "A" not in mod.g.hist_na_pending


def test_p6_first_weak_frame_holds(mod):
    cnt, trig, note = mod._p6_weak_step("A", 45.0)

    assert cnt == 1
    assert trig is False
    assert "hold" in note
    assert "A" in mod.g.p6_weak


def test_p6_second_weak_frame_triggers(mod):
    mod._p6_weak_step("A", 45.0)

    cnt, trig, note = mod._p6_weak_step("A", 44.0)

    assert cnt == 2
    assert trig is True
    assert "sell" in note
    assert "A" not in mod.g.p6_weak


def test_p6_window_expiry_restarts_count(mod):
    mod.g.p6_weak["A"] = {"cnt": 1, "ts": time.time() - 31.0, "score": 45.0}

    cnt, trig, _ = mod._p6_weak_step("A", 44.0)

    assert cnt == 1
    assert trig is False


def test_p6_recovery_resets_count(mod):
    mod._p6_weak_step("A", 45.0)

    mod._p6_weak_reset("A")

    assert "A" not in mod.g.p6_weak
