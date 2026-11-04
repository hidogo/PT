# -*- coding: utf-8 -*-
"""v1.27 预期三态口径：S-1 开盘涨幅基准（含负基/零基）、放量烂板独立三态、
一字/近一字开盘档位、中位硬规避。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location(
        "buysell_core_v127_expected_three_states_test", STRATEGY_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(
        info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None
    )
    m._sn = lambda sec: sec
    m._save_state = lambda: None
    m.g = SimpleNamespace(
        exp={},
        exp_file={},
        zt_lianban={},
        spot={},
        auction_c={},
        skip_log_ts={},
    )
    return m


def _seed_auction(mod, sec, chg):
    mod._auction_change = lambda s: chg
    mod._auction_ready = lambda s: True


def test_auction_benchmark_negative_and_zero_are_valid(mod):
    """S-1 负开/平开都是合法基准，不再用 >0 过滤。"""
    mod.g.exp_file["A"] = {
        "has_expected_auction": True,
        "expected_auction_change_pct": -0.93,
    }
    v, has = mod._auction_benchmark("A")
    assert has is True and v == -0.93

    mod.g.exp_file["B"] = {
        "has_expected_auction": True,
        "expected_auction_change_pct": 0.0,
    }
    v, has = mod._auction_benchmark("B")
    assert has is True and v == 0.0

    mod.g.exp_file["C"] = {"has_expected_auction": False, "expected_auction_change_pct": 0.0}
    mod._hist_window = lambda s: ([10.0, 10.0], [9.0, 10.0])
    v, has = mod._auction_benchmark("C")
    assert has is True and abs(v - 11.111111111111116) < 1e-9

    mod.g.exp_file["D"] = {"has_expected_auction": False, "expected_auction_change_pct": 0.0}
    mod._hist_window = lambda s: (None, None)
    v, has = mod._auction_benchmark("D")
    assert has is False


def test_confirm_expected_negative_basis_compare(mod):
    """竞价涨幅高于 S-1 开盘涨幅（负基也可）即竞价超预期。"""
    mod.g.exp_file["A"] = {
        "side": "buy",
        "expected_status": "pending_exceed",
        "has_expected_auction": True,
        "expected_auction_change_pct": -0.93,
    }
    mod._auction_change = lambda s: 1.5
    st, actual = mod._confirm_expected("A")
    assert st == mod.CX and actual == 1.5

    mod._auction_change = lambda s: -1.0
    st, _ = mod._confirm_expected("A")
    assert st == mod.PM


def test_confirm_expected_missing_basis_keeps_pm(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "expected_status": "pending_exceed",
        "has_expected_auction": False,
        "expected_auction_change_pct": 0.0,
    }
    mod._auction_change = lambda s: 5.0
    mod._hist_window = lambda s: (None, None)
    st, actual = mod._confirm_expected("A")
    assert st == mod.PM and actual == 5.0


def test_eval_auction_bad_seal_three_states(mod):
    """放量烂板/炸板不回封：红开=超预期、小绿=符合、大绿/跌停=低于。"""
    mod.g.exp_file["A"] = {"role_detail": "bad_seal_board", "entry_type": "normal"}
    _seed_auction(mod, "A", 0.5)
    st, reasons = mod._eval_auction("A")
    assert st == mod.PX and "bad_seal_red_open_exceed" in reasons

    _seed_auction(mod, "A", -1.0)
    st, reasons = mod._eval_auction("A")
    assert st == mod.PM and "bad_seal_small_green_meet" in reasons

    _seed_auction(mod, "A", -2.1)
    st, reasons = mod._eval_auction("A")
    assert st == mod.PS and "bad_seal_big_green_miss" in reasons


def test_exp_rt_bad_seal_pending_miss_red_open_intraday_confirm(mod):
    """bad seal 基础三态为 miss 时，红开超预期仍可走盘中确认，不被静态 expect_miss 放弃。"""
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_miss",
        "role_detail": "bad_seal_board",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    _seed_auction(mod, "A", 0.5)
    mod._two_1m_break = lambda s: True
    mod._limit_up_within_1m = lambda s: False
    mod._below_vwap_confirm = lambda s: False
    st, reason = mod._exp_rt_status("A")
    assert st == mod.CX and "bad_seal_intraday_exceed" in reason


def test_exp_rt_bad_seal_red_open_observes_without_confirm(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_miss",
        "role_detail": "broken_consecutive_limit_up",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    _seed_auction(mod, "A", 0.5)
    mod._two_1m_break = lambda s: False
    mod._limit_up_within_1m = lambda s: False
    mod._below_vwap_confirm = lambda s: False
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "observe_bad_seal_red_open" in reason


def test_exp_rt_bad_seal_small_green_meet(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_miss",
        "role_detail": "bad_seal_board",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    _seed_auction(mod, "A", -1.0)
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "bad_seal_small_green_meet" in reason


def test_exp_rt_bad_seal_big_green_miss(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_miss",
        "role_detail": "bad_seal_board",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    _seed_auction(mod, "A", -2.1)
    st, reason = mod._exp_rt_status("A")
    assert st == mod.CS and "bad_seal_green_open_miss" in reason


def test_exp_rt_bad_seal_auction_awaiting_not_miss(mod):
    """bad seal 竞价数据未就绪保持等待，不误判大绿放弃。"""
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_miss",
        "role_detail": "bad_seal_board",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    mod._auction_change = lambda s: 0.0
    mod._auction_ready = lambda s: False
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "bad_seal_auction_awaiting" in reason


def test_eval_auction_missing_yesterday_open_keeps_awaiting(mod):
    mod.g.exp_file["A"] = {"role_detail": "", "entry_type": "normal"}
    _seed_auction(mod, "A", 2.0)
    mod._yesterday_open_chg = lambda s: (0.0, False)
    st, reasons = mod._eval_auction("A")
    assert st == mod.AW and "missing_yesterday_open" in reasons


def test_exp_rt_exceed_negative_basis_and_intraday_confirm(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_exceed",
        "has_expected_auction": True,
        "expected_auction_change_pct": -0.93,
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    mod._auction_change = lambda s: 1.5
    mod._auction_ready = lambda s: True
    mod._two_1m_break = lambda s: True
    mod._limit_up_within_1m = lambda s: False
    mod._below_vwap_confirm = lambda s: False
    st, reason = mod._exp_rt_status("A")
    assert st == mod.CX and "intraday_exceed" in reason


def test_exp_rt_exceed_missing_basis_awaits_not_miss(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_exceed",
        "has_expected_auction": False,
        "expected_auction_change_pct": 0.0,
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    mod._auction_change = lambda s: 5.0
    mod._auction_ready = lambda s: True
    mod._hist_window = lambda s: (None, None)
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "await_intraday_confirm" in reason


def test_exp_rt_meet_requires_intraday_confirm(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "normal",
        "expected_status": "pending_meet",
        "seal_amount_t0": 0.0,
    }
    mod._resync_buy_entry_type = lambda s: "normal"
    mod._auction_change = lambda s: 2.0
    mod._auction_ready = lambda s: True
    mod._two_1m_break = lambda s: False
    mod._limit_up_within_1m = lambda s: False
    mod._below_vwap_confirm = lambda s: False
    mod._intraday_confirmed_ready = lambda s: True
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "meet_wait_intraday_confirm" in reason


def test_exp_rt_one_word_open_below_min_miss(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "one_word",
        "expected_status": "pending_exceed",
        "seal_amount_t0": 100000.0,
    }
    mod._resync_buy_entry_type = lambda s: "one_word"
    mod._auction_change = lambda s: 7.0
    mod._auction_ready = lambda s: True
    mod._exp_one_word = lambda s, quiet=False: (mod.CM, ["seal_within"])
    st, reason = mod._exp_rt_status("A")
    assert st == mod.CS and "one_word_open_below_min" in reason


def test_exp_rt_one_word_open_ok_stays_seal_wait(mod):
    mod.g.exp_file["A"] = {
        "side": "buy",
        "entry_type": "one_word",
        "expected_status": "pending_exceed",
        "seal_amount_t0": 100000.0,
    }
    mod._resync_buy_entry_type = lambda s: "one_word"
    mod._auction_change = lambda s: 10.0
    mod._auction_ready = lambda s: True
    mod._exp_one_word = lambda s, quiet=False: (mod.CM, ["seal_within"])
    st, reason = mod._exp_rt_status("A")
    assert st == mod.PM and "seal_wait" in reason


def test_mid_board_avoid_authoritative_mid_hard_skip(mod):
    mod.g.exp_file["A"] = {"role_detail": "mid_consecutive_limit_up"}
    mod.g.zt_lianban["A"] = {"board_cnt": 3, "unique_high": True}
    assert mod._mid_board_avoid("A") is True


def test_mid_board_avoid_no_authority_keeps_unique_fallback(mod):
    mod.g.exp_file["A"] = {"role_detail": ""}
    mod.g.zt_lianban["A"] = {"board_cnt": 3, "unique_high": True}
    mod._dyn_theme_leader = lambda s: False
    assert mod._mid_board_avoid("A") is False

    mod.g.zt_lianban["A"]["unique_high"] = False
    assert mod._mid_board_avoid("A") is True
