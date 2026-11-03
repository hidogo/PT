# -*- coding: utf-8 -*-
"""v1.28 P2E 持仓自身反证：题材联动不覆盖超预期个股（澳洋健康类）、
确认段审计日志、T+1 可卖 0 审计真实值。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location(
        "buysell_core_v128_p2e_reverse_test", STRATEGY_PATH
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
    m._p2e_reverse_log = lambda sec, msg: None
    m._p2e_skip_log = lambda sec, msg: None
    m._unique_stand = lambda sec: False
    m._is_one_word_open = lambda sec: False
    m.g = SimpleNamespace(
        exp={},
        exp_file={},
        zt_lianban={},
        spot={},
        auction_c={},
        zt_theme={},
        zt_themes_of={},
        p2e_reverse_log={},
        p2e_skip_log={},
    )
    return m


def _seed_theme(mod, holding, mid, mid_chg):
    mod.g.zt_theme = {"T": {"members": {holding, mid}}}
    mod.g.zt_themes_of = {holding: ["T"], mid: ["T"]}
    mod.g.zt_lianban = {mid: {"board_cnt": 3}}
    mod._auction_change = lambda s: mid_chg if s == mid else -3.0
    mod._auction_benchmark = lambda s: (-0.93, True)
    mod._auction_ready = lambda s: True


def test_p2e_theme_mid_break_reverse_bad_seal_red_open(mod):
    """bad seal 红开超预期：题材中位崩塌不直接清仓，交盘中分时反证。"""
    mod.g.exp_file["A"] = {"side": "hold", "role_detail": "bad_seal_board", "entry_type": "normal"}
    _seed_theme(mod, "A", "MID", -5.2)
    mod._auction_change = lambda s: 5.8 if s == "A" else -5.2
    mod._eval_auction = lambda s: (mod.PX, ["bad_seal_red_open_exceed"]) if s == "A" else (mod.PS, ["auction_green_open"])
    mod._confirm_expected = lambda s: (mod.PM, 5.8)
    lines = []
    mod._p2e_reverse_log = lambda sec, msg: lines.append(msg)
    hit, note, rev = mod._p2e_core_sell_check("A")
    assert hit is False and rev is True
    assert any("题材中位崩塌被自身反证豁免" in x for x in lines)


def test_p2e_theme_mid_break_reverse_file_cx(mod):
    """exceed 持仓实时 CX：题材联动反证豁免。"""
    mod.g.exp_file["A"] = {"side": "hold", "expected_status": "pending_exceed", "entry_type": "normal"}
    _seed_theme(mod, "A", "MID", -5.2)
    mod._auction_change = lambda s: 5.8 if s == "A" else -5.2
    mod._eval_auction = lambda s: (mod.PM, ["auction_small_open"])
    mod._confirm_expected = lambda s: (mod.CX, 5.8)
    hit, note, rev = mod._p2e_core_sell_check("A")
    assert hit is False and rev is True


def test_p2e_theme_mid_break_reverse_one_word_sealed(mod):
    """一字封死持仓：题材联动反证豁免。"""
    mod.g.exp_file["A"] = {"side": "hold", "entry_type": "one_word"}
    _seed_theme(mod, "A", "MID", -5.2)
    mod._auction_change = lambda s: -5.2
    mod._eval_auction = lambda s: (mod.AW, ["one_word_requires_seal"])
    mod._confirm_expected = lambda s: (mod.PM, 0.0)
    mod._is_one_word_open = lambda s: True
    hit, note, rev = mod._p2e_core_sell_check("A")
    assert hit is False and rev is True


def test_p2e_theme_mid_break_hits_when_holding_green(mod):
    """持仓自身绿开：题材中位崩塌仍核卖（P1 大绿开兜底）。"""
    mod.g.exp_file["A"] = {"side": "hold", "entry_type": "normal"}
    _seed_theme(mod, "A", "MID", -5.2)
    mod._auction_change = lambda s: -3.0 if s == "A" else -5.2
    mod._eval_auction = lambda s: (mod.PS, ["auction_green_open"])
    mod._confirm_expected = lambda s: (mod.PM, -3.0)
    hit, note, rev = mod._p2e_core_sell_check("A")
    assert hit is True and rev is False
    assert "P2E_theme_mid_break" in note


def test_p2e_reverse_guard_disabled_keeps_hit(mod):
    """反证总开关关闭：题材联动恢复核卖。"""
    mod.BLS["p2e_reverse_guard_enabled"] = False
    mod.g.exp_file["A"] = {"side": "hold", "role_detail": "bad_seal_board", "entry_type": "normal"}
    _seed_theme(mod, "A", "MID", -5.2)
    mod._auction_change = lambda s: 5.8 if s == "A" else -5.2
    mod._eval_auction = lambda s: (mod.PX, ["bad_seal_red_open_exceed"]) if s == "A" else (mod.PS, ["auction_green_open"])
    mod._confirm_expected = lambda s: (mod.PM, 5.8)
    hit, note, rev = mod._p2e_core_sell_check("A")
    assert hit is True and rev is False


def test_p2e_hook_audit_heartbeat_and_reverse(mod):
    """确认段逐票评估 + heartbeat + 跳过计数。"""
    lines = []
    mod.log = SimpleNamespace(
        info=lambda msg: lines.append(msg), error=lambda msg: None, warning=lambda msg: None
    )
    mod._set_now = lambda ctx: None
    mod._hhmmss = lambda: "09:24:48"
    mod.get_trading_day = lambda: "20261103"
    mod._load_expectation = lambda merge=False: None
    mod._sellable_source = lambda: {"A": {}, "B": {}}
    mod._norm_sec = lambda raw: raw
    mod._sellable = lambda raw, positions: 100
    mod._sell_inflight = lambda sec: False
    mod._p2e_core_sell_check = lambda sec: (True, "P2E_theme_mid_break", False) if sec == "A" else (False, "", True)
    mod._do_sell = lambda *a, **k: None
    mod.g = SimpleNamespace(
        p2e_warm_logged=False,
        p2e_fresh_day=None,
        auction_c={},
        exp_file={"A": {}},
        sold_log={},
        zt_theme={},
        p2e_heartbeat_ts=0,
        p2e_end_logged=False,
        p2e_skip_log={},
        p2e_reverse_log={},
    )
    mod.p2e_auction_core_sell(object())
    joined = "\n".join(lines)
    assert "[P2E-heartbeat]" in joined
    assert "eval=2 hit=1 reverse=1 skip=0" in joined
    assert "[P2E] A hms=09:24:48 hit=1 reverse=0" in joined


def test_sell_amt0_audit_logs_actual_avail_value(mod):
    """T+1 当日买入可卖 0 审计：avail_val 打印字段真实值，不误读为数量。"""
    mod._sellable_detail = lambda raw, positions: (0, "enable_amount", True, True)
    mod._sellable_total = lambda raw, positions: (800, "amount", True)
    mod.g.daily = {"bought": ["600000.XSHG"], "sold": []}
    mod.g.bought_qty = {"600000.XSHG": 800}
    lines = []
    mod._audit_sell_skip = lambda sec, why: lines.append(why)
    mod._audit_sell_amt0("600000.XSHG", "600000.XSHG", {})
    assert any("avail_present=1 avail_val=0 total_field=amount total_qty=800 total_present=1 t1=1 bought_qty=800" in x for x in lines)
