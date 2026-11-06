# -*- coding: utf-8 -*-
"""v1.44 CORE 标签：连板>=3 且热门板块命中（题材梯队名次<=3 / 新题材发酵 confirmed/hot）。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v144_core_tag_hot_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS["core_tag_hot_rank_max"] = 3
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._limitup_days = lambda sec: 3
    m._is_100day_high = lambda sec: None
    m._zt_themes_of = lambda sec: []
    m._new_themes_of = lambda sec: []
    m._dyn_theme_ferment = lambda: {}
    m.g = SimpleNamespace(zt_theme={})
    return m


def test_core_requires_hot_theme_rank(mod):
    mod._zt_themes_of = lambda sec: ["T"]
    mod.g.zt_theme = {"T": {"rank": 2}}
    assert "CORE" in mod._tags("A")


def test_core_blocks_non_hot_rank(mod):
    mod._zt_themes_of = lambda sec: ["T"]
    mod.g.zt_theme = {"T": {"rank": 5}}
    assert "CORE" not in mod._tags("A")


def test_core_blocks_no_theme(mod):
    assert "CORE" not in mod._tags("A")


def test_core_allows_new_theme_confirmed(mod):
    mod._new_themes_of = lambda sec: ["THS:新概念"]
    mod._dyn_theme_ferment = lambda: {"THS:新概念": {"confirmed": True}}
    assert "CORE" in mod._tags("A")


def test_core_allows_new_theme_hot_stage(mod):
    mod._new_themes_of = lambda sec: ["THS:新概念"]
    mod._dyn_theme_ferment = lambda: {"THS:新概念": {"stage": "hot"}}
    assert "CORE" in mod._tags("A")


def test_core_requires_three_boards(mod):
    mod._limitup_days = lambda sec: 2
    mod._zt_themes_of = lambda sec: ["T"]
    mod.g.zt_theme = {"T": {"rank": 1}}
    tags = mod._tags("A")
    assert "CORE" not in tags
    assert "LB" in tags


def test_lb_bs_unchanged(mod):
    mod._limitup_days = lambda sec: 2
    mod._is_100day_high = lambda sec: True
    tags = mod._tags("A")
    assert "LB" in tags
    assert "BS" in tags
    assert "CORE" not in tags


def test_core_rank_max_param_applies(mod):
    mod._zt_themes_of = lambda sec: ["T"]
    mod.g.zt_theme = {"T": {"rank": 4}}
    assert "CORE" not in mod._tags("A")
    mod.BLS["core_tag_hot_rank_max"] = 5
    assert "CORE" in mod._tags("A")
