import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_strategy_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "exp_direction_enabled": True,
        "exp_direction_attack_bonus": 0.8,
        "exp_direction_avoid_hard_skip": True,
        "exp_direction_hot_front_only": True,
        "exp_direction_rotate_leader_exception": True,
        "exp_direction_log": False,
        "daily_max_buy": 10,
        "cold_secs": 60,
        "exp_order_pct": 0.10,
        "board_buy_budget_ratio": 0.20,
        "EXPECT_ORDER": False,
    })
    return mod


def _direction(kind="neutral", score=0.0, hard_skip=False, reason="test"):
    return {
        "kind": kind,
        "score": score,
        "hard_skip": hard_skip,
        "size_mult": 1.0,
        "theme": "",
        "role": "outside",
        "stage": "watch",
        "phase": "watch",
        "reason": reason,
    }


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m.g = SimpleNamespace(zt_lianban={"A": {"board_cnt": 4}})
    m._lb_senti_phase = lambda: {"phase": "high_continue"}
    m._lb_senti_tier = lambda sec: "mid"
    m._zt_themes_of = lambda sec: ["R"]
    m._new_themes_of = lambda sec: []
    m._dyn_theme_status = lambda: {"R": {"leader": "", "max_board_dyn": 0}}
    m._dyn_theme_ferment = lambda: {}
    return m


def test_attack_high_adds_sort_score_without_size_change(mod):
    mod._dyn_theme_status = lambda: {"R": {"leader": "A", "max_board_dyn": 4}}
    before = (mod.BLS["exp_order_pct"], mod.BLS["board_buy_budget_ratio"])

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["score"] == pytest.approx(0.8)
    assert ctx["hard_skip"] is False
    assert ctx["size_mult"] == 1.0
    assert (mod.BLS["exp_order_pct"], mod.BLS["board_buy_budget_ratio"]) == before


def test_attack_high_keeps_static_unique_before_limit_touch(mod):
    mod.g.zt_lianban["A"]["unique_high"] = 1
    mod._dyn_theme_status = lambda: {"R": {"leader": "", "max_board_dyn": 0}}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["score"] == pytest.approx(0.8)


def test_attack_low_uses_confirmed_new_theme_front(mod):
    mod._lb_senti_phase = lambda: {"phase": "rotate_low"}
    mod._lb_senti_tier = lambda sec: "low"
    mod._zt_themes_of = lambda sec: []
    mod._new_themes_of = lambda sec: ["THS:robot"]
    mod._dyn_theme_ferment = lambda: {
        "THS:robot": {"confirmed": True, "stage": "confirmed", "front": "A"}
    }

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_low"
    assert ctx["score"] == pytest.approx(0.8)
    assert ctx["theme"] == "THS:robot"


def test_hot_rear_is_hard_skipped(mod):
    mod._zt_themes_of = lambda sec: []
    mod._new_themes_of = lambda sec: ["THS:robot"]
    mod._dyn_theme_ferment = lambda: {
        "THS:robot": {"confirmed": True, "stage": "hot", "front": "B"}
    }

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "avoid"
    assert ctx["hard_skip"] is True
    assert ctx["reason"] == "hot_rear"


def test_rotate_low_mid_follower_is_skipped(mod):
    mod._lb_senti_phase = lambda: {"phase": "rotate_low"}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "avoid"
    assert ctx["hard_skip"] is True
    assert ctx["reason"] == "mid_high_rotate_low"


def test_rotate_low_allows_original_unique_leader_exception(mod):
    mod._lb_senti_phase = lambda: {"phase": "rotate_low"}
    mod._dyn_theme_status = lambda: {"R": {"leader": "A", "max_board_dyn": 4}}

    ctx = mod._exp_direction_eval("A")
    allowed, note = mod._lb_senti_buy_gate("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["reason"] == "origin_leader_rotate_exception"
    assert allowed is True
    assert "origin_unique_leader_ok" in note


def test_missing_direction_data_falls_back_to_neutral(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}
    mod._zt_themes_of = lambda sec: []
    mod._new_themes_of = lambda sec: []

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "neutral"
    assert ctx["score"] == 0.0
    assert ctx["hard_skip"] is False


def test_all_expected_sources_share_one_priority_queue(mod):
    calls = []
    mod.g = SimpleNamespace(
        exp_file={
            "P": {"side": "buy", "_src": "provider"},
            "Q": {"side": "buy", "_src": "zt_pool"},
        },
        daily={"bought": []},
    )
    mod._min_age = lambda: 0
    mod._exp_direction_eval = lambda code: _direction()
    mod._pool_exp_priority = lambda code, direction=None: (-1.0 if code == "Q" else 0.0, 0)
    mod._attempt_expected_buy = lambda context, code, direction=None: calls.append(code)

    mod._try_expected_buys(SimpleNamespace())

    assert calls == ["Q", "P"]


def test_avoid_is_removed_before_attempt(mod):
    calls = []
    mod.g = SimpleNamespace(
        exp_file={"A": {"side": "buy"}, "B": {"side": "buy"}},
        daily={"bought": []},
    )
    mod._min_age = lambda: 0
    mod._exp_direction_eval = lambda code: (
        _direction("avoid", hard_skip=True) if code == "A" else _direction()
    )
    mod._exp_direction_log = lambda sec, ctx, action: None
    mod._pool_exp_priority = lambda code, direction=None: (0.0, 0)
    mod._attempt_expected_buy = lambda context, code, direction=None: calls.append(code)

    mod._try_expected_buys(SimpleNamespace())

    assert calls == ["B"]


def test_pm_is_not_upgraded_by_attack_direction(mod):
    placed = []
    mod.g = SimpleNamespace(exp_fired=set(), buy_log={}, exp={}, daily={"bought": []})
    mod._mid_board_avoid = lambda sec: False
    mod._lb_senti_buy_gate = lambda sec: (True, "normal")
    mod.trade_open = lambda sec: True
    mod._exp_rt_status = lambda sec: (mod.PM, "observe_test")
    mod.place_expected_order = lambda context, sec, note="": placed.append((sec, note)) or True
    mod._exp_direction_log = lambda sec, ctx, action: None

    mod._attempt_expected_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})),
                              "A", direction=_direction("attack_low", 0.8))

    assert placed == []


def test_cx_order_note_logs_direction_but_keeps_position_ratio(mod):
    captured = {}
    notes = []
    mod.g = SimpleNamespace(
        exp_fired=set(), buy_log={}, exp={}, daily={"bought": []},
        spot={"A": {"up_px": 10.0}}, pending={},
    )
    mod._mid_board_avoid = lambda sec: False
    mod._lb_senti_buy_gate = lambda sec: (True, "normal")
    mod.trade_open = lambda sec: True
    mod._exp_rt_status = lambda sec: (mod.CX, "intraday_exceed(1.0%)")
    mod._dyn_unq_confirmed = lambda sec: False
    mod._save_state = lambda: None
    mod._exp_direction_log = lambda sec, ctx, action: None
    mod._rt_lag_info = lambda sec: (0.0, "ok")
    mod.last_px = lambda sec: 9.8
    mod._avail_cash = lambda context: 1_000_000.0
    mod._block_sealed_buy = lambda sec: False
    mod._order_limit = lambda sec, side, mode: 9.8

    def _calc(context, sec, px, ratio):
        captured["ratio"] = ratio
        return 100

    mod._calc_buy_qty = _calc
    mod._buy_pos_ok = lambda context, sec, qty, limit: True
    mod._signal = lambda *args, **kwargs: None

    def _place(context, sec, note=""):
        notes.append(note)
        return True

    mod.place_expected_order = _place
    mod._attempt_expected_buy(SimpleNamespace(portfolio=SimpleNamespace(positions={})),
                              "A", direction=_direction("attack_low", 0.8))

    assert notes and "dir=attack_low" in notes[0]
    assert "size_mult=1.0" in notes[0]
    assert captured == {}


def test_place_expected_order_ratio_is_independent_of_direction(mod):
    captured = {}
    mod.g = SimpleNamespace(spot={"A": {"up_px": 11.0}}, pending={})
    mod._mid_board_avoid = lambda sec: False
    mod._rt_lag_info = lambda sec: (0.0, "ok")
    mod.last_px = lambda sec: 10.5
    mod._avail_cash = lambda context: 1_000_000.0
    mod._block_sealed_buy = lambda sec: False
    mod._order_limit = lambda sec, side, mode: 10.5

    def _calc(context, sec, px, ratio):
        captured["ratio"] = ratio
        return 100

    mod._calc_buy_qty = _calc
    mod._buy_pos_ok = lambda context, sec, qty, limit: True
    mod._signal = lambda *args, **kwargs: None

    ok = mod.place_expected_order(SimpleNamespace(), "A", note="direction ignored here")

    assert ok is True
    assert captured["ratio"] == pytest.approx(mod.BLS["exp_order_pct"])


def test_attack_score_scales_after_1000_without_zeroing(mod):
    mod._lb_senti_t100_passed = lambda: True
    mod.score_now = lambda sec: 0.0
    mod._dyn_unq_confirmed = lambda sec: False
    mod._zt_theme_sort_bonus = lambda sec: 0.0
    mod._first_zt_ms = lambda sec: 0

    prio = mod._pool_exp_priority("A", direction=_direction("attack_low", 0.8))

    assert prio[0] == pytest.approx(-0.4)


def test_t100_freeze_records_direction_counts(mod):
    state = {"mid": {"phase": "rotate_low"}, "auction": {}}
    mod.g = SimpleNamespace(exp_file={
        "A": {"side": "buy"},
        "B": {"side": "buy"},
        "S": {"side": "sell"},
    })
    mod._set_now = lambda context: None
    mod._hhmm = lambda: "10:00"
    mod._lb_senti_state = lambda: state
    mod._lb_senti_mid = lambda force=False: {
        "promo": 0.2, "break_rate": 0.3, "red": 0.5, "low_assist": 3, "new_dir_n": 2,
    }
    mod._exp_direction_eval = lambda code: {
        "kind": "attack_low" if code == "A" else "avoid"
    }
    mod._save_state = lambda: None

    mod.lb_senti_t100_freeze(SimpleNamespace())

    assert state["t100"]["direction"] == {
        "attack_high": 0, "attack_low": 1, "neutral": 0, "avoid": 1,
    }
