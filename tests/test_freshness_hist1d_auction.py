import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_freshness_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


class FakeDf:
    def __init__(self, closes, index_dates):
        self.close = list(closes)
        self.index = list(index_dates)

    def __len__(self):
        return len(self.close)

    def __getitem__(self, key):
        if key == "close":
            return self.close
        if key == "volume":
            return [100.0] * len(self.close)
        if key == "low":
            return self.close
        raise KeyError(key)


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m.g = SimpleNamespace(
        hist_na_pending={},
        hist_prio_cache={},
        score_na_pending={},
        zt_lianban={},
        exp_file={},
        spot={},
        auction_c={},
        skip_log_ts={},
        _name_map={},
    )
    m.get_trading_day = lambda: "2026-11-01"
    m.get_positions = lambda: []
    m._get_snapshot_many = lambda secs, n: {}
    m.last_px = lambda sec: 0.0
    return m


def test_100day_high_excludes_unfinished_today_row(mod):
    mod._hist_1d = lambda sec, prio=0, ttl=None: FakeDf(
        [10.0, 11.0, 12.0, 13.0, 999.0],
        ["2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"],
    )
    mod.last_px = lambda sec: 15.0

    assert mod._is_100day_high("A") is True

    mod.last_px = lambda sec: 12.9
    assert mod._is_100day_high("A") is False


def test_100day_high_missing_hist_is_pending_not_false(mod):
    mod._hist_1d = lambda sec, prio=0, ttl=None: None

    assert mod._is_100day_high("A") is None
    assert "A" in mod.g.hist_na_pending


def test_hist_priority_marks_exp_position_and_core(mod):
    mod.g.exp_file = {"B": {"side": "buy"}}
    mod.g.zt_lianban = {"C": {"board_cnt": 3}}
    mod.g.hist_prio_cache = {"tok": int(time.time() / 5.0), "set": {"B", "P", "C"}}

    assert mod._is_hist_priority("B") is True
    assert mod._is_hist_priority("P") is True
    assert mod._is_hist_priority("C") is True
    assert mod._is_hist_priority("X") is False


def test_hist1d_prewarm_only_uses_prio_one(mod):
    calls = []
    mod._pool = lambda: ["B", "X"]
    mod.get_positions = lambda: []
    mod.g.exp_file = {"B": {"side": "buy"}}
    mod.g.zt_lianban = {"C": {"board_cnt": 3}}
    mod.g.hist_prio_cache = {"tok": int(time.time() / 5.0), "set": {"B", "C"}}
    mod._hist_1d = lambda sec, prio=0, ttl=None: (calls.append((sec, prio)) or FakeDf(
        [1.0, 2.0], ["2026-10-29", "2026-10-30"]))

    ok = mod._hist1d_prewarm("09:25")

    assert ok == 2
    assert ("B", 1) in calls
    assert ("C", 1) in calls
    assert all(prio == 1 for _, prio in calls)


def test_score_recover_prioritizes_core_within_cap(mod):
    mod.BLS["score_recover_probe_cap_fast"] = 1
    mod._lb_senti_t100_passed = lambda: False
    mod._spot_ready = lambda sec: True
    mod._board_strength_info = lambda sec: (1.0, True)
    mod.score_now = lambda sec: 60.0
    mod.g.hist_prio_cache = {"tok": int(time.time() / 5.0), "set": {"core1"}}
    mod.g.score_na_pending = {
        "core1": {"ts": time.time() - 100, "prio": 1},
        "low1": {"ts": time.time() - 100, "prio": 0},
    }
    mod.g.hist_na_pending = {}

    mod._score_recover_probe()

    assert "core1" not in mod.g.score_na_pending
    assert "low1" in mod.g.score_na_pending


def test_fill_zt_spot_returns_got_and_missing(mod):
    mod.g.zt_lianban = {"A": {"board_cnt": 2}, "B": {"board_cnt": 2}}
    mod.g.spot = {
        "A": {"open_px": 10.0, "preclose_px": 10.0},
        "B": {"open_px": 0.0, "preclose_px": 10.0},
    }
    mod._get_snapshot_many = lambda secs, n: {"B": {"open_px": 9.5, "preclose_px": 10.0}}

    got, missing = mod._fill_zt_spot()
    assert got == 1
    assert missing == []

    mod.g.spot["B"] = {"open_px": 0.0, "preclose_px": 10.0}
    mod._get_snapshot_many = lambda secs, n: {}
    got, missing = mod._fill_zt_spot()
    assert got == 0
    assert missing == ["B"]
