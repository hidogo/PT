import datetime
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
    m.get_trading_day = lambda: "20261026"
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
    mod.g = SimpleNamespace(spot={"A": {"up_px": 11.0, "last_px": 10.5,
                                        "open_px": 10.5, "wavg_px": 10.5}}, pending={})
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


def test_watch_static_unique_high_gets_attack_high(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}
    mod.g.zt_lianban["A"]["unique_high"] = 1
    mod._dyn_theme_status = lambda: {"R": {"leader": "", "max_board_dyn": 0}}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["score"] == pytest.approx(0.8)
    assert ctx["reason"] == "origin_leader_watch_preconfirm"
    assert ctx["hard_skip"] is False


def test_watch_dynamic_unique_leader_gets_attack_high(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}
    mod._dyn_theme_status = lambda: {"R": {"leader": "A", "max_board_dyn": 4}}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["reason"] == "origin_leader_watch_preconfirm"


def test_watch_confirmed_new_theme_front_gets_attack_low(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}
    mod._lb_senti_tier = lambda sec: "low"
    mod._zt_themes_of = lambda sec: []
    mod._new_themes_of = lambda sec: ["THS:robot"]
    mod._dyn_theme_ferment = lambda: {
        "THS:robot": {"confirmed": True, "stage": "confirmed", "front": "A"}
    }

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_low"
    assert ctx["score"] == pytest.approx(0.8)
    assert ctx["reason"] == "new_theme_front_watch"


def test_watch_confirmed_old_theme_front_mid_gets_attack_high(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}
    mod._dyn_theme_ferment = lambda: {
        "R": {"confirmed": True, "stage": "confirmed", "front": "A"}
    }

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "attack_high"
    assert ctx["reason"] == "theme_ferment_front_watch"


def test_watch_ordinary_mid_stays_neutral_without_hard_skip(mod):
    mod._lb_senti_phase = lambda: {"phase": "watch"}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "neutral"
    assert ctx["score"] == 0.0
    assert ctx["hard_skip"] is False


def test_ice_wait_mid_follower_still_avoided(mod):
    mod._lb_senti_phase = lambda: {"phase": "ice_wait"}

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "avoid"
    assert ctx["hard_skip"] is True
    assert ctx["reason"] == "mid_high_ice_wait"


def test_high_diverg_static_unique_leader_still_avoided(mod):
    mod._lb_senti_phase = lambda: {"phase": "high_diverg"}
    mod.g.zt_lianban["A"]["unique_high"] = 1

    ctx = mod._exp_direction_eval("A")

    assert ctx["kind"] == "avoid"
    assert ctx["hard_skip"] is True
    assert ctx["reason"] == "mid_high_high_diverg"


# ================= v0.73：首帧误弃 / 一字重标 / 竞价唯一可信门 / L2 逐票播种 =================
def _mk_g(**kw):
    g = SimpleNamespace(
        zt_lianban={},
        spot={},
        exp={},
        exp_file={},
        l2_big={},
        l2_big_probed=set(),
        l2_big_seeded=set(),
        l2_big_seed_onjoin_ts=0.0,
        l2_big_seed_onjoin_px={},
        l2_big_log_ts={},
        below_vwap_pending={},
        _name_map={},
    )
    for k, v in kw.items():
        setattr(g, k, v)
    return g


def test_vwap_weak_first_frame_grace_and_confirm(mod):
    mod.g = _mk_g(spot={"A": {"wavg_px": 10.0, "up_px": 11.0, "last_px": 9.5}})
    age = {"v": 5.0}
    mod._sec_age = lambda: age["v"]

    assert mod._below_vwap_confirm("A") is False      # 首帧宽限不判弱
    assert "A" in mod.g.below_vwap_pending

    age["v"] = 40.0
    assert mod._below_vwap_confirm("A") is True       # 连续弱确认
    assert "A" not in mod.g.below_vwap_pending


def test_vwap_weak_at_limit_exempt(mod):
    mod.g = _mk_g(spot={"A": {"wavg_px": 10.0, "up_px": 10.0, "last_px": 10.0}})
    mod._sec_age = lambda: 100.0

    assert mod._below_vwap_confirm("A") is False      # 贴板豁免，即使 wavg 微大于现价


def test_vwap_weak_recovers_clears_pending(mod):
    mod.g = _mk_g(spot={"A": {"wavg_px": 10.0, "up_px": 11.0, "last_px": 9.5}})
    mod._sec_age = lambda: 5.0

    assert mod._below_vwap_confirm("A") is False
    mod.g.spot["A"]["wavg_px"] = 9.0
    assert mod._below_vwap_confirm("A") is False
    assert "A" not in mod.g.below_vwap_pending


def test_buy_entry_type_resync_to_one_word(mod):
    mod.g = _mk_g(
        exp_file={"A": {"side": "buy", "entry_type": "normal", "expected_status": "pending_exceed"}},
        spot={"A": {"open_px": 10.0, "up_px": 10.0, "last_px": 10.0}},
    )

    assert mod._resync_buy_entry_type("A") == "one_word"
    assert mod.g.exp_file["A"]["entry_type"] == "one_word"


def test_buy_entry_type_resync_back_to_normal(mod):
    mod.g = _mk_g(
        exp_file={"A": {"side": "buy", "entry_type": "one_word", "expected_status": "pending_exceed"}},
        spot={"A": {"open_px": 9.0, "up_px": 10.0, "last_px": 9.5}},
    )

    assert mod._resync_buy_entry_type("A") == "normal"
    assert mod.g.exp_file["A"]["entry_type"] == "normal"


def test_buy_entry_type_resync_skips_hold(mod):
    mod.g = _mk_g(
        exp_file={"H": {"side": "hold", "entry_type": "normal", "expected_status": "pending_meet"}},
        spot={"H": {"open_px": 10.0, "up_px": 10.0, "last_px": 10.0}},
    )

    assert mod._resync_buy_entry_type("H") == "normal"


def test_dyn_unq_unmapped_board_not_unique(mod):
    mod.g = _mk_g(
        zt_lianban={"A": {"board_cnt": 1}, "B": {"board_cnt": 1}},
        exp_file={
            "A": {"side": "buy", "expected_status": "pending_exceed", "entry_type": "normal"},
            "B": {"side": "buy", "expected_status": "pending_exceed", "entry_type": "normal"},
        },
    )
    mod._auction_board_of = lambda sec: None

    mod._dyn_unq_auction_eval()
    st = mod.g.dyn_unq["auction"]
    assert st["A"]["mapped"] is False
    assert st["A"]["unique"] is False


def test_dyn_unq_mapped_peer_exceed_is_not_unique(mod):
    mod.g = _mk_g(
        zt_lianban={"A": {"board_cnt": 1}, "B": {"board_cnt": 1}},
        exp_file={
            "A": {"side": "buy", "expected_status": "pending_exceed", "entry_type": "normal"},
            "B": {"side": "buy", "expected_status": "pending_exceed", "entry_type": "normal"},
        },
    )
    mod._auction_board_of = lambda sec: "B1"

    mod._dyn_unq_auction_eval()
    st = mod.g.dyn_unq["auction"]
    assert st["A"]["mapped"] is True
    assert st["A"]["peer_cnt"] == 1
    assert st["A"]["peer_exceed"] == 1
    assert st["A"]["unique"] is False


def test_dyn_unq_mapped_no_peer_exceed_is_unique(mod):
    mod.g = _mk_g(
        zt_lianban={"A": {"board_cnt": 1}, "B": {"board_cnt": 1}},
        exp_file={
            "A": {"side": "buy", "expected_status": "pending_exceed", "entry_type": "normal"},
            "B": {"side": "buy", "expected_status": "pending_meet", "entry_type": "normal"},
        },
    )
    mod._auction_board_of = lambda sec: "B1"

    mod._dyn_unq_auction_eval()
    st = mod.g.dyn_unq["auction"]
    assert st["A"]["mapped"] is True
    assert st["A"]["unique"] is True


def test_l2_seed_onjoin_per_stock_no_global_throttle(mod):
    calls = []

    def _seed(secs, pages=5):
        calls.append(list(secs))
        mod.g.l2_big_seeded.update(secs)

    mod._l2_big_seed = _seed
    mod._log_l2_big_seed_summary = lambda sec: None
    mod.g = _mk_g(
        l2_big_seeded=set(),
        l2_big_seed_onjoin_px={},
        l2_big_seed_onjoin_ts=999999999999.0,   # 旧全局节流已消耗，不应阻塞新票
    )

    mod._l2_big_seed_onjoin(["A", "B"])
    assert calls == [["A"], ["B"]]


def test_l2_seed_onjoin_per_frame_cap(mod):
    calls = []

    def _seed(secs, pages=5):
        calls.append(list(secs))
        mod.g.l2_big_seeded.update(secs)

    mod._l2_big_seed = _seed
    mod._log_l2_big_seed_summary = lambda sec: None
    mod.BLS["l2_big_seed_onjoin_max_per_frame"] = 1
    mod.g = _mk_g(l2_big_seeded=set(), l2_big_seed_onjoin_px={})

    mod._l2_big_seed_onjoin(["A", "B"])
    assert calls == [["A"]]
    mod._l2_big_seed_onjoin(["A", "B"])
    assert calls == [["A"], ["B"]]


# ================= v0.74：首笔灵敏度（near_scan 覆盖增强 + 帧内最早一笔） =================
def test_tx_frame_zt_ms_takes_earliest_row(mod):
    import pandas as pd

    mod.g = _mk_g(spot={"A": {"up_px": 10.0}})
    frame = {"A": {"transaction": pd.DataFrame([
        {"business_time": 20261026093058500, "hq_px": 10.0},
        {"business_time": 20261026093100000, "hq_px": 10.0},
    ])}}

    assert mod._tx_frame_zt_ms("A", frame) == 20261026093058500


def test_tx_zt_batch_raw_backfills_earlier_firstzt_ms(mod):
    dh = mod.DataHub()
    fields = ["business_time", "hq_px", "business_amount", "trade_index"]
    _day = datetime.date.today().strftime("%Y%m%d")
    _ms_early = int(_day + "093058500")
    _ms_frame = int(_day + "093100000")
    raw = {
        "fields": fields,
        "A": [
            [_ms_early, 10.0, 1000000, "t1"],
            [_ms_frame, 10.0, 500000, "t2"],
        ],
    }
    dh._tx_pull_raw = lambda secs: raw
    mod.g = _mk_g(
        spot={"A": {"up_px": 10.0}},
        l2_big={},
        l2_big_probed=set(),
        l2_big_wm={},
        l2_dir_dist={},
    )
    frame = {"A": {"transaction": {"business_time": _ms_frame, "hq_px": 10.0}}}

    out = dh.tx_zt_batch(["A"], frame)

    assert out["A"] == _ms_early


def test_tick_targets_includes_near_scan_before_watch(mod):
    mod.BLS["tick_board_scan"] = False
    mod.BLS["universe"] = []
    mod.BLS["tick_near_cap"] = 12
    mod.BLS["tick_watch_cap"] = 15
    mod.g = _mk_g(
        pool_static=[],
        watch=["W"],
        near_scan={"N1": {"ts": 1.0, "round": 1, "chg": 8.0}},
        first_zt={},
    )
    mod.get_positions = lambda: []

    out = mod._tick_targets()

    assert "N1" in out
    assert out.index("N1") < out.index("W")


def test_tick_targets_excludes_first_zt_from_near_scan(mod):
    mod.BLS["tick_board_scan"] = False
    mod.BLS["universe"] = []
    mod.g = _mk_g(
        pool_static=[],
        watch=[],
        near_scan={
            "DONE": {"ts": 1.0, "round": 1, "chg": 9.0},
            "LIVE": {"ts": 2.0, "round": 1, "chg": 8.0},
        },
        first_zt={"DONE": {"ts": 1.0}},
    )
    mod.get_positions = lambda: []

    out = mod._tick_targets()

    assert "LIVE" in out
    assert "DONE" not in out


def test_tick_seed_cands_merges_near_scan_and_skips_first_zt(mod):
    mod.g = _mk_g(
        near_scan={"N1": {"ts": 1.0, "round": 1, "chg": 8.0}},
        first_zt={"DONE": {"ts": 1.0}},
    )
    mod.g.near_scan["DONE"] = {"ts": 1.0, "round": 1, "chg": 9.0}

    cands = mod._tick_seed_cands(["A"])

    assert cands == ["A", "N1"]
    assert "DONE" not in cands


def test_scan_order_hot_first_and_near_scan_collect(mod):
    mod.BLS["scan_hot_first"] = True
    mod.BLS["first_board_minute"] = 10
    mod.BLS["scan_batch"] = 600
    mod.BLS["max_watch"] = 50
    mod.BLS["scan_min_chg"] = 3.0
    mod.BLS["scan_near_chg"] = 7.0
    mod.BLS["scan_near_cap"] = 20
    mod.BLS["scan_near_keep_rounds"] = 3
    mod.g = _mk_g(
        pool_all=[],
        pool_day=None,
        watch=[],
        scan_order=[],
        scan_order_day=None,
        scan_round=0,
        scan_offset=0,
        zt_lianban={"H.XSHG": {"board_cnt": 2}},
        selfwatch=[],
        pool_static=[],
        exp_file={},
        first_zt={},
    )
    mod.get_trading_day = lambda: "20261026"
    mod.get_Ashares = lambda: ["H.XSHG", "C1.XSHG", "C2.XSHG"]
    mod._get_snapshot_many = lambda window, cap: {
        c: {"preclose_px": 10.0, "last_px": 10.8, "up_px": 11.0} for c in window
    }
    mod._min_age = lambda: 5
    mod._hhmm = lambda: "09:35"

    out = mod._scan_market()

    assert mod.g.scan_order[0] == "H.XSHG"
    assert mod.g.near_scan
    assert "H.XSHG" in mod.g.watch
    assert set(mod.g.watch) == {"H.XSHG", "C1.XSHG", "C2.XSHG"}


# ================= v0.75：盘中定期保存 / 重启重建 first_zt / 全链路剔除 ST =================
def test_is_st_uses_zt_authoritative_and_name_fallback(mod):
    mod.BLS["skip_st_pool"] = True
    mod.get_trading_day = lambda: "20261026"
    mod.g = _mk_g(
        zt_lianban={"A": {"is_st": True}, "B": {"is_st": False}},
        _name_map={},
        st_set=set(),
        st_day=None,
    )

    assert mod._is_st("A") is True
    assert mod._is_st("B") is False

    mod.g.zt_lianban = {}
    mod.get_stock_name = lambda sec: "*ST测试" if sec == "S.XSHG" else "正常"
    assert mod._is_st("S.XSHG") is True
    assert mod._is_st("N.XSHG") is False
    assert "S.XSHG" in mod.g.st_set


def test_scan_market_excludes_st_from_watch_and_near(mod):
    mod.BLS.update({
        "scan_hot_first": True,
        "first_board_minute": 10,
        "scan_batch": 600,
        "max_watch": 50,
        "scan_min_chg": 3.0,
        "scan_near_chg": 7.0,
        "scan_near_cap": 20,
        "scan_near_keep_rounds": 3,
        "skip_st_pool": True,
    })
    mod.get_trading_day = lambda: "20261026"
    mod.get_Ashares = lambda: ["S.XSHG", "C1.XSHG", "C2.XSHG"]
    mod._get_snapshot_many = lambda window, cap: {
        c: {"preclose_px": 10.0, "last_px": 10.8, "up_px": 11.0} for c in window
    }
    mod._min_age = lambda: 5
    mod._hhmm = lambda: "09:35"
    mod._warm_name_map = lambda secs: None
    mod.g = _mk_g(
        pool_all=[],
        pool_day=None,
        watch=[],
        scan_order=[],
        scan_order_day=None,
        scan_round=0,
        scan_offset=0,
        zt_lianban={
            "S.XSHG": {"is_st": True},
            "C1.XSHG": {"is_st": False},
            "C2.XSHG": {"is_st": False},
        },
        selfwatch=[],
        pool_static=[],
        exp_file={},
        first_zt={},
        near_scan={},
        st_skip_log_ts=0.0,
    )

    out = mod._scan_market()

    assert "S.XSHG" not in out
    assert "S.XSHG" not in mod.g.watch
    assert "S.XSHG" not in mod.g.near_scan


def test_tick_targets_keeps_position_st_and_skips_candidates(mod):
    mod.BLS["tick_board_scan"] = False
    mod.BLS["universe"] = []
    mod.BLS["tick_near_cap"] = 12
    mod.BLS["tick_watch_cap"] = 15
    mod.BLS["skip_st_pool"] = True
    mod._warm_name_map = lambda secs: None
    mod.get_positions = lambda: ["POSST.XSHG"]
    mod.g = _mk_g(
        pool_static=["PST.XSHG", "POK.XSHG"],
        watch=["WST.XSHG", "WOK.XSHG"],
        near_scan={
            "NST.XSHG": {"ts": 1.0, "round": 1, "chg": 8.0},
            "NOK.XSHG": {"ts": 2.0, "round": 1, "chg": 8.0},
        },
        first_zt={},
        zt_lianban={
            "PST.XSHG": {"is_st": True},
            "WST.XSHG": {"is_st": True},
            "NST.XSHG": {"is_st": True},
            "POK.XSHG": {"is_st": False},
            "WOK.XSHG": {"is_st": False},
            "NOK.XSHG": {"is_st": False},
        },
    )

    out = mod._tick_targets()

    assert "POSST.XSHG" in out
    assert "PST.XSHG" not in out
    assert "WST.XSHG" not in out
    assert "NST.XSHG" not in out
    assert "POK.XSHG" in out
    assert "WOK.XSHG" in out
    assert "NOK.XSHG" in out


def test_handle_data_saves_state_with_60s_throttle(mod):
    calls = []
    mod._save_state = lambda: calls.append(1)
    mod._set_now = lambda context: None
    mod.refresh_spot = lambda context: None
    mod._maybe_roll_day = lambda: False
    mod.sell_manager = lambda context: None
    mod._try_expected_buys = lambda context: None
    mod.BLS.update({
        "debug_score": False,
        "scan_enabled": False,
        "selfwatch_enabled": False,
        "daily_max_buy": 10,
        "ma5_pullback": False,
        "state_save_interval": 60.0,
    })
    mod.g = SimpleNamespace(
        bar_counter=0,
        one_word_marked_open=True,
        l2_probed=True,
        last_save_ts=0.0,
        daily={"bought": ["X"] * 10},
    )
    fake = SimpleNamespace(clock=[1000.0])
    fake.time = lambda: fake.clock[0]
    mod.time = fake

    mod.handle_data(SimpleNamespace(), SimpleNamespace())
    assert calls == [1]

    fake.clock[0] += 30.0
    mod.handle_data(SimpleNamespace(), SimpleNamespace())
    assert calls == [1]

    fake.clock[0] += 60.0
    mod.handle_data(SimpleNamespace(), SimpleNamespace())
    assert calls == [1, 1]


def test_rebuild_queue_skips_existing_and_st(mod):
    mod.BLS["skip_st_pool"] = True
    mod._pool = lambda: ["A", "B", "S"]
    mod.get_positions = lambda: []
    mod.get_trading_day = lambda: "20261026"
    mod.g = _mk_g(
        first_zt={"A": {"ts": 1.0}},
        zt_lianban={
            "A": {"is_st": False},
            "B": {"is_st": False},
            "S": {"is_st": True},
        },
        exp_file={},
        first_zt_rebuild_pending=[],
    )

    mod._rebuild_first_zt_queue()

    assert mod.g.first_zt_rebuild_pending == ["B"]


def test_rebuild_first_zt_falls_back_to_hs_timestamp_and_is_idempotent(mod):
    mod.BLS["skip_st_pool"] = True
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: {}
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={"A": {"is_st": False}},
        l2_big={"A": {"first_ts": 20261026100000000}},
        spot={"A": {"last_px": 10.0, "up_px": 10.0, "hsTimeStamp": 20261026100000000}},
        first_zt_rebuild_pending=["A"],
        first_zt_rebuild_retry_ts={},
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    mod._rebuild_first_zt_tick()

    ft = mod.g.first_zt["A"]
    assert ft["src"] == "restart_rebuild_fallback"
    assert ft["ms"] == 20261026100000000
    assert mod.g.first_zt_rebuild_pending == []

    mod._rebuild_first_zt_tick()   # 幂等：已有记录不再重建
    assert len(mod.g.first_zt) == 1


def test_rebuild_first_zt_takes_earliest_limit_tx_not_tickdir_first_ts(mod):
    mod.BLS["skip_st_pool"] = True
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: {
        "fields": ["business_time", "hq_px"],
        "A": [[20261026093500000, 9.9], [20261026095000000, 10.0], [20261026100000000, 10.0]],
    }
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={"A": {"is_st": False}},
        l2_big={"A": {"first_ts": 20261026093500000}},
        spot={"A": {"last_px": 9.9, "up_px": 10.0}},
        first_zt_rebuild_pending=["A"],
        first_zt_rebuild_retry_ts={},
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    mod._rebuild_first_zt_tick()

    ft = mod.g.first_zt["A"]
    assert ft["src"] == "restart_rebuild"
    assert ft["ms"] == 20261026095000000   # 涨停价最早成交，而不是 tickdir 首笔 09:35


# ================= v0.76：重启重建不阻塞 / 破板可重建 / 重试节流 / heartbeat / 1m 兜底 =================
def test_rebuild_first_zt_missing_spot_does_not_block_later_batch(mod):
    mod.BLS["skip_st_pool"] = True
    mod.BLS["first_zt_rebuild_cap"] = 5
    mod.BLS["first_zt_rebuild_retry_sec"] = 30.0
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    mod._get_ds = lambda: SimpleNamespace(snapshot=lambda secs: None)
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: {
        "fields": ["business_time", "hq_px"],
        "OK.XSHG": [[20261026095000000, 10.0]],
    }
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={c: {"is_st": False} for c in ["W1", "W2", "W3", "W4", "W5", "OK.XSHG"]},
        l2_big={},
        spot={"OK.XSHG": {"last_px": 10.0, "up_px": 10.0}},
        first_zt_rebuild_pending=["W1", "W2", "W3", "W4", "W5", "OK.XSHG"],
        first_zt_rebuild_retry_ts={},
        restart_rebuild_hb_ts=0.0,
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    # 第一帧：前 5 只缺 spot -> wait 并冷却，不重建
    mod._rebuild_first_zt_tick()
    assert "OK.XSHG" not in mod.g.first_zt
    assert set(mod.g.first_zt_rebuild_pending) == {"W1", "W2", "W3", "W4", "W5", "OK.XSHG"}

    # 第二帧：前 5 只仍在 30s 冷却、不占 cap，OK.XSHG 可推进重建
    mod._rebuild_first_zt_tick()
    assert mod.g.first_zt["OK.XSHG"]["ms"] == 20261026095000000
    assert mod.g.first_zt["OK.XSHG"]["src"] == "restart_rebuild"
    assert set(mod.g.first_zt_rebuild_pending) == {"W1", "W2", "W3", "W4", "W5"}


def test_rebuild_first_zt_rebuilds_broken_board(mod):
    mod.BLS["skip_st_pool"] = True
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: {
        "fields": ["business_time", "hq_px"],
        "A": [[20261026103000000, 10.0]],
    }
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={"A": {"is_st": False}},
        l2_big={},
        spot={"A": {"last_px": 9.5, "up_px": 10.0}},   # 已破板
        first_zt_rebuild_pending=["A"],
        first_zt_rebuild_retry_ts={},
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    mod._rebuild_first_zt_tick()

    assert mod.g.first_zt["A"]["ms"] == 20261026103000000
    assert mod.g.first_zt["A"]["src"] == "restart_rebuild"


def test_rebuild_first_zt_never_limited_stock_does_not_fallback(mod):
    mod.BLS["skip_st_pool"] = True
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: {}
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={"A": {"is_st": False}},
        l2_big={},
        spot={"A": {"last_px": 9.5, "up_px": 10.0, "hsTimeStamp": 20261026143000000}},
        first_zt_rebuild_pending=["A"],
        first_zt_rebuild_retry_ts={},
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    mod._rebuild_first_zt_tick()

    assert "A" not in mod.g.first_zt          # 未涨停且无逐笔证据：不能靠快照时间戳误建
    assert mod.g.first_zt_rebuild_pending == ["A"]
    assert mod.g.first_zt_rebuild_retry_ts["A"] > 0


def test_rebuild_first_zt_retry_throttle_and_heartbeat(mod):
    real_time = mod.time
    now = [1000.0]
    mod.time = SimpleNamespace(time=lambda: now[0], localtime=real_time.localtime)
    mod.BLS["skip_st_pool"] = True
    mod.BLS["first_zt_rebuild_retry_sec"] = 30.0
    mod.BLS["first_zt_rebuild_heartbeat_sec"] = 60.0
    mod.get_trading_day = lambda: "20261026"
    mod._seal_metrics = lambda sec: (1000.0, 10)
    mod._snap_vol = lambda s: 100.0
    mod._l2_big_turnover = lambda sec: 1000.0
    calls = {"tx": 0}
    mod.get_individual_transaction = lambda secs, data_count=200, is_dict=True: (
        calls.__setitem__("tx", calls["tx"] + 1) or {})
    hb_logs = []
    mod.log.info = lambda msg: hb_logs.append(str(msg))
    mod.g = _mk_g(
        first_zt={},
        zt_lianban={"A": {"is_st": False}},
        l2_big={},
        spot={"A": {"last_px": 10.0, "up_px": 10.0}},
        first_zt_rebuild_pending=["A"],
        first_zt_rebuild_retry_ts={},
        restart_rebuild_hb_ts=0.0,
        now_dt=datetime.datetime(2026, 10, 26, 9, 30, 0),
    )

    mod._rebuild_first_zt_tick()          # 逐笔空 -> wait，30s 冷却
    assert mod.g.first_zt_rebuild_pending == ["A"]
    assert mod.g.first_zt_rebuild_retry_ts["A"] == 1000.0

    mod._rebuild_first_zt_tick()          # 冷却中：不重试、不拉 API
    assert calls["tx"] == 1

    now[0] += 31.0
    mod._rebuild_first_zt_tick()          # 冷却解除：降级失败仍 wait，不产生 first_zt
    assert calls["tx"] == 2
    assert "A" not in mod.g.first_zt

    hb = [m for m in hb_logs if m.startswith("[restart-rebuild] pending=")]
    assert len(hb) == 1                   # 60s 节流只打一次


def test_handle_data_1m_calls_rebuild_fallback(mod):
    calls = []
    mod._set_now = lambda context: None
    mod.refresh_spot = lambda context: None
    mod._maybe_roll_day = lambda: False
    mod.sell_manager = lambda context: None
    mod._try_expected_buys = lambda context: None
    mod._rebuild_first_zt_tick = lambda: calls.append("rb")
    mod.BLS.update({
        "debug_score": False,
        "scan_enabled": False,
        "selfwatch_enabled": False,
        "daily_max_buy": 10,
        "ma5_pullback": False,
        "restart_rebuild_1m_enabled": True,
    })
    mod.g = SimpleNamespace(
        bar_counter=0,
        one_word_marked_open=True,
        l2_probed=True,
        daily={"bought": ["X"] * 10},
    )

    mod.handle_data(SimpleNamespace(), SimpleNamespace())
    assert calls == ["rb"]
