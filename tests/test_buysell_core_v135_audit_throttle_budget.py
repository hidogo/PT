# -*- coding: utf-8 -*-
"""v1.35 持仓字段 dump / 日志节流 / 午后预算降频 / 延迟汇总回归测试。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v135_audit_throttle_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


def _logger():
    logs = []
    return SimpleNamespace(info=lambda msg: logs.append(msg), error=lambda msg: None,
                           warning=lambda msg: None), logs


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log, m._logs = _logger()
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-04"
    m.g = SimpleNamespace(
        daily={"bought": [], "sold": []},
        bought_qty={},
        first_zt={},
        sweep_a_ld_buy={},
        t1_pending_sell={},
        t1_pending_log_ts={},
        t1_pending_cnt={},
        t1_pending_save_ts=0.0,
        pos_raw_dump_log={},
        seal_low_tail_log_ts={},
        tx_lag_stats={"cnt": 0, "sum": 0.0, "max": 0.0, "sample": ""},
        budget_over_acc={},
        budget_over_peak={},
        budget_log_ts=0.0,
        first_zt_rebuild_gave_up=set(),
        first_zt_rebuild_zt_hit={},
        skip_log_ts={},
    )
    return m


def _t1_stubs(mod):
    mod.last_px = lambda sec: 10.0
    mod.my_cost = lambda raw, positions: 9.0
    mod._role_tolerance = lambda sec: {"green_tol": 1.0, "stop_adj": 1.0}
    mod._auction_change = lambda sec: 1.0
    mod._p2e_core_sell_check = lambda sec: (False, "")
    mod.get_stop_loss_pct = lambda sec: 0.05
    mod._p7a_check = lambda sec, q: False
    mod._p7b_check = lambda sec, q: False
    mod._p7d_check = lambda sec, q: False
    mod._lb_senti_cut_hold = lambda sec: False
    mod._ld_theme_hit = lambda sec: {}


def test_source_limit_afternoon_limits(mod):
    mod._min_age = lambda: 45
    mod._hhmm = lambda: "10:15"
    assert mod._source_limit("board") == float(mod.BLS["frame_board_limit_afternoon"])
    assert mod._source_limit("hist1d") == float(mod.BLS["frame_hist1d_limit_afternoon"])
    assert mod._source_limit("hist1d", prio=1) == float(mod.BLS["frame_hist1d_prio_limit_afternoon"])
    assert mod._source_limit("m1") == float(mod.BLS["frame_m1_limit"])


def test_source_limit_tail_idle_blocks_noncore_board_hist1d(mod):
    mod._min_age = lambda: 300
    mod._hhmm = lambda: "14:46"
    assert mod._source_limit("board") == 0.0
    assert mod._source_limit("hist1d") == 0.0
    assert mod._source_limit("snapshot") > 0.0
    assert mod._source_limit("board", prio=1) > 0.0


def test_pos_dump_once_per_day_with_full_fields(mod):
    pos = {"amount": 0, "enable_amount": 0, "can_use_qty": 400, "symbol": "603533"}
    mod._audit_pos_fields("603533.XSHG", pos)
    assert len(mod._logs) == 1
    assert "[pos-dump]" in mod._logs[0] and "can_use_qty" in mod._logs[0] and "400" in mod._logs[0]
    mod._audit_pos_fields("603533.XSHG", pos)
    assert len(mod._logs) == 1


def test_sellable_detail_dumps_pos_when_avail_zero(mod):
    positions = {"603533.XSHG": {"amount": 0, "enable_amount": 0, "can_use_qty": 400}}
    qty, key, avail_present, total_present = mod._sellable_detail("603533.XSHG", positions)
    assert qty == 0 and key == "enable_amount" and avail_present and total_present
    assert "603533.XSHG" in mod.g.pos_raw_dump_log
    assert any("[pos-dump]" in x for x in mod._logs)


def test_t1_protect_first_full_then_heartbeat(mod):
    _t1_stubs(mod)
    mod.g.daily["bought"] = ["603533.XSHG"]
    mod.g.bought_qty["603533.XSHG"] = 300
    positions = {"603533.XSHG": {"amount": 300, "enable_amount": 0}}
    mod._t1_protect_capture("603533.XSHG", "603533.XSHG", positions)
    assert len(mod._logs) == 1 and "记录保护触发" in mod._logs[0]
    mod._t1_protect_capture("603533.XSHG", "603533.XSHG", positions)
    assert len(mod._logs) == 1  # 300s 心跳窗口内不重复
    mod.g.t1_pending_log_ts["603533.XSHG"] = time.time() - 301.0
    mod._t1_protect_capture("603533.XSHG", "603533.XSHG", positions)
    assert len(mod._logs) == 2 and "累计 2 次" in mod._logs[1]


def test_seal_low_tail_log_throttled_without_fast_flag(mod):
    mod._is_tail_auction = lambda: True
    ft = {"seal_low_fast": False, "seal_low": False}
    mod._update_seal_low_state(ft, "A", 4.0, 4.5, 0.0, 0, True, 1000.0, 0.333, 0.15)
    mod._update_seal_low_state(ft, "A", 4.0, 4.5, 0.0, 0, True, 1000.0, 0.333, 0.15)
    assert len(mod._logs) == 1 and "tail_auction=1" in mod._logs[0]
    assert ft.get("seal_low_fast") is False  # 尾盘保持两帧降级语义


def test_tx_lag_stats_accumulate(mod):
    now = time.time()
    mod.g.first_zt["A"] = {"ms": int(time.strftime("%Y%m%d%H%M%S", time.localtime(now - 100))) * 1000,
                           "ts": now, "src": "tx"}
    mod._skip_log = lambda *a, **k: None
    mod._tx_lag_warn("A")
    st = mod.g.tx_lag_stats
    assert st["cnt"] == 1 and st["max"] > 90.0 and "A" in st["sample"]


def test_restart_rebuild_later_log_once(mod):
    mod.g.first_zt_rebuild_gave_up.add("A")
    mod._restart_rebuild_later_log("A")
    assert len(mod._logs) == 1 and "rebuilt_later" in mod._logs[0]
    assert "A" not in mod.g.first_zt_rebuild_gave_up
    mod._restart_rebuild_later_log("A")
    assert len(mod._logs) == 1


def test_budget_over_peak_updated(mod):
    mod._get_ds = lambda: SimpleNamespace(
        frame_report=lambda: "board=6/6 hist1d=10/10 over:board=910,hist1d=350,hist1d_p=119",
        frame={"over": {"board": 910, "hist1d": 350, "hist1d_p": 119}},
        degraded=set(),
    )
    mod._skip_log = lambda *a, **k: None
    mod._budget_log()
    assert mod.g.budget_over_peak.get("board") == 910
    assert mod.g.budget_over_peak.get("hist1d") == 350
