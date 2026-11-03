# -*- coding: utf-8 -*-
"""v1.29 收盘集合竞价 SEAL_LOW_FAST 降级两帧确认：
14:57-15:00 封单归零不触发一帧卖出，保留 tail_auction 审计标记。"""
import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location(
        "buysell_core_v129_tail_auction_test", STRATEGY_PATH
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
    m.g = SimpleNamespace(now_dt=None)
    return m


def _fast_call(mod, ft, tail=False):
    mod._is_tail_auction = lambda: tail
    mod._update_seal_low_state(ft, "A", 10.0, 11.0, 0, 0, True, 1000000.0, 0.333, 0.15)


def test_tail_auction_fast_downgrades_to_two_frame(mod):
    """尾盘竞价段 FAST 不置 seal_low_fast，只走两帧确认并打 tail_auction=1。"""
    ft = {}
    _fast_call(mod, ft, tail=True)
    assert ft.get("seal_low") is True
    assert not ft.get("seal_low_fast")
    assert ft.get("tail_auction") is True
    assert ft.get("seal_low_confirm_ts") is not None


def test_normal_fast_still_one_frame(mod):
    """非尾盘竞价段保持 1 帧 FAST 灵敏度。"""
    ft = {}
    _fast_call(mod, ft, tail=False)
    assert ft.get("seal_low") is True
    assert ft.get("seal_low_fast") is True
    assert not ft.get("tail_auction")


def test_tail_auction_recover_clears_flag(mod):
    """封单恢复后撤销 SEAL_LOW 并清除 tail_auction 标记。"""
    ft = {}
    _fast_call(mod, ft, tail=True)
    mod._is_tail_auction = lambda: True
    mod._update_seal_low_state(ft, "A", 10.0, 11.0, 500000.0, 3, True, 1000000.0, 0.333, 0.15)
    assert ft.get("seal_low") is False
    assert not ft.get("seal_low_fast")
    assert not ft.get("tail_auction")


def test_tail_auction_window_boundary(mod):
    """14:57 起进入尾盘竞价段，15:00 退出。"""
    mod.g.now_dt = datetime(2026, 11, 3, 14, 56, 59)
    assert mod._is_tail_auction() is False
    mod.g.now_dt = datetime(2026, 11, 3, 14, 57, 0)
    assert mod._is_tail_auction() is True
    mod.g.now_dt = datetime(2026, 11, 3, 14, 59, 59)
    assert mod._is_tail_auction() is True
    mod.g.now_dt = datetime(2026, 11, 3, 15, 0, 0)
    assert mod._is_tail_auction() is False
