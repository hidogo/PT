# -*- coding: utf-8 -*-
"""v1.31 云端近期情绪温度历史 + 阶段消费（方向排序/P8 轮次清仓）。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v131_senti_hist_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    mod.BLS.update({
        "senti_hist_enabled": True,
        "senti_hist_keep_days": 10,
        "cold_streak_min": 3,
        "theme_overheat_zt_min": 20,
        "warm_confirm_front_bonus": 0.4,
        "stage_rear_round_enabled": True,
        "stage_rear_cut_ratio": 0.5,
        "stage_rear_max_rounds": 3,
        "stage_rear_round_gap_sec": 60.0,
        "senti_stage_cache_sec": 15.0,
        "sentiment_ice_ratio": 0.40,
        "sentiment_warm_min": 0.45,
        "sentiment_warm_base": 0.55,
        "sentiment_warm_decay": 0.02,
        "warm_taper_start": 3,
        "lb_senti_cut_enabled": True,
        "lb_senti_cut_half_ratio": 0.5,
    })
    return mod


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log = SimpleNamespace(info=lambda msg: None, error=lambda msg: None, warning=lambda msg: None)
    m._warn = lambda msg: None
    m._save_state = lambda: None
    m.get_trading_day = lambda: "2026-11-03"
    m._market_red_ratio = lambda: 0.60
    m._senti_theme_zt_n = lambda: (0, '')
    m._lb_senti_phase = lambda: {'phase': 'watch'}
    m.g = SimpleNamespace(
        sentiment=None,
        senti_hist={},
        senti_stage_cache=None,
        senti_stage_sell_log={},
        lb_senti={},
        lb_senti_cache={},
        zt_lianban={},
        zt_theme={},
        zt_themes_of={},
        zt_new_cache={'ts': 0.0, 'data': {}},
        zt_dyn_cache={},
        zt_ferment_cache={},
        zt_ferment_stage={},
        zt_unmapped_n=0,
        boards={},
        stock_boards={},
        first_zt={},
        dyn_unq=None,
        daily=m._new_daily(),
        spot={},
        buy_log={},
    )
    return m


def _base(mod, **kw):
    d = {
        'date': '2026-11-02', 'ice': False, 'ice_streak': 0, 'warm_days': 0,
        'divergence': False, 'emotion': '', 'emotion_basis': '', 'phase': '',
    }
    d.update(kw)
    mod.g.sentiment = d


def test_hist_window_trim_and_idempotent(mod):
    mod.g.senti_hist = {
        '2026-10-%02d' % i: {'day': '2026-10-%02d' % i, 'date': '2026-10-%02d' % i}
        for i in range(20, 31)
    }
    mod.g.lb_senti = {
        'day': '2026-11-03',
        'auction': {'ready': True, 'mid_open_rate': 0.6},
        't100': {'phase': 'high_diverg', 'direction': {}},
    }
    mod._senti_hist_save = lambda: 0
    r1 = mod._senti_hist_touch('auction')
    r2 = mod._senti_hist_touch('t100')
    assert r1 is not None and r2 is not None
    assert mod.g.senti_hist['2026-11-03'] is r2
    assert r2.get('auction') and r2.get('t100')
    assert len(mod.g.senti_hist) <= 10
    assert '2026-11-03' in mod.g.senti_hist


def test_baseline_hist_fallback_when_csv_missing(mod):
    mod.g.sentiment = None
    mod.g.senti_hist = {
        '2026-11-02': {
            'ice': True, 'ice_streak': 2, 'warm_days': 0, 'divergence': False,
            'stage_flags': ['cold'],
        }
    }
    base = mod._senti_baseline()
    assert base.get('hist_fallback') is True
    assert base.get('ice') is True
    assert base.get('ice_streak') == 2


def test_cold_streak_deep_ice(mod):
    _base(mod, ice=True, ice_streak=4)
    mod._market_red_ratio = lambda: 0.20
    out = mod._senti_stage(force=True)
    assert 'cold' in out['flags']
    assert 'deep_ice' in out['flags']


def test_warm_confirm_day(mod):
    _base(mod, ice=True, ice_streak=3)
    mod._market_red_ratio = lambda: 0.65
    out = mod._senti_stage(force=True)
    assert 'warm_confirm_day' in out['flags']
    assert 'cold' not in out['flags']


def test_warm_continue(mod):
    _base(mod, ice=False, warm_days=2)
    mod._market_red_ratio = lambda: 0.60
    out = mod._senti_stage(force=True)
    assert 'warm_continue' in out['flags']


def test_theme_first_burst_not_overheat(mod):
    _base(mod, ice=False)
    mod._senti_theme_zt_n = lambda: (25, 'T')
    out = mod._senti_stage(force=True)
    assert 'first_burst' in out['flags']
    assert 'theme_overheat' not in out['flags']


def test_theme_overheat_after_prior_burst(mod):
    _base(mod, ice=False)
    mod.g.senti_hist = {
        '2026-11-02': {
            'theme_zt_n': 25, 'theme_zt_name': 'T', 'first_burst_themes': ['T'],
            'date': '2026-11-02',
        }
    }
    mod._senti_theme_zt_n = lambda: (22, 'T')
    out = mod._senti_stage(force=True)
    assert 'theme_overheat' in out['flags']
    assert 'first_burst' not in out['flags']
    assert 'diverging' in out['flags']


def test_diverging_from_baseline(mod):
    _base(mod, ice=False, warm_days=2, divergence=True)
    out = mod._senti_stage(force=True)
    assert 'diverging' in out['flags']


def test_warm_confirm_front_sort_bonus(mod):
    mod.score_now = lambda code: 0.0
    mod._dyn_unq_confirmed = lambda sec: False
    mod._zt_theme_sort_bonus = lambda code: 0.0
    mod._lb_senti_participate_scale = lambda: 1.0
    mod._first_zt_ms = lambda code: None
    dctx = {'kind': 'attack_low', 'score': 0.8}
    mod._senti_stage = lambda force=False: {'flags': {'warm_confirm_day'}}
    warm = mod._pool_exp_priority('A', direction=dctx)
    mod._senti_stage = lambda force=False: {'flags': set()}
    base = mod._pool_exp_priority('A', direction=dctx)
    assert warm < base


def test_p8_stage_rear_rounds(mod):
    mod._lb_senti_phase = lambda: {'phase': 'high_diverg'}
    mod._today_zt = lambda sec: False
    mod._senti_stage = lambda force=False: {'flags': {'theme_overheat', 'diverging'}}
    mod._lb_senti_tier = lambda sec: 'low'
    mod._senti_rear_exempt = lambda sec: False
    r1 = mod._lb_senti_cut_hold('A')
    assert r1 and r1[0] == 0.5 and 'round=1' in r1[1]
    mod._mark_lb_cut('A')
    assert mod.g.lb_senti['cut_seen']['A']['round'] == 1
    assert mod._lb_senti_cut_hold('A') is None   # 60s 间隔未到
    mod.g.lb_senti['cut_seen']['A']['ts'] = time.time() - 61
    r2 = mod._lb_senti_cut_hold('A')
    assert r2 and 'round=2' in r2[1]
    mod._mark_lb_cut('A')
    mod.g.lb_senti['cut_seen']['A']['ts'] = time.time() - 61
    r3 = mod._lb_senti_cut_hold('A')
    assert r3 and 'round=3' in r3[1]
    mod._mark_lb_cut('A')
    assert mod._lb_senti_cut_hold('A') is None   # 达到最大轮次


def test_p8_stage_rear_exempt(mod):
    mod._lb_senti_phase = lambda: {'phase': 'high_diverg'}
    mod._today_zt = lambda sec: False
    mod._senti_stage = lambda force=False: {'flags': {'theme_overheat', 'diverging'}}
    mod._lb_senti_tier = lambda sec: 'low'
    mod._senti_rear_exempt = lambda sec: True
    mod.g.lb_senti.setdefault('cut_seen', {}).clear()
    assert mod._lb_senti_cut_hold('A') is None


def test_p8_original_mid_single_shot(mod):
    mod._lb_senti_phase = lambda: {'phase': 'high_diverg'}
    mod._today_zt = lambda sec: False
    mod._senti_stage = lambda force=False: {'flags': set()}
    mod._lb_senti_tier = lambda sec: 'mid'
    mod.g.lb_senti.setdefault('cut_seen', {}).clear()
    r = mod._lb_senti_cut_hold('C')
    assert r and 'P8_lb_senti_cut_half' in r[1]
    mod._mark_lb_cut('C')
    assert mod._lb_senti_cut_hold('C') is None


def test_legacy_ts_cut_counts_one_round(mod):
    mod.g.lb_senti = {'day': '2026-11-03', 'cut_seen': {'D': time.time()}}
    assert mod._lb_cut_round('D') == 1


def test_stage_does_not_change_pos_cap(mod):
    _base(mod, ice=True, ice_streak=1)
    mod._market_red_ratio = lambda: 0.70
    cap = mod._sentiment_pos_cap(SimpleNamespace(portfolio=SimpleNamespace(positions={})), 'A')
    assert cap == 0.8
    out = mod._senti_stage(force=True)
    assert 'warm_confirm_day' in out['flags']


def test_corrupted_file_degrades(tmp_path, mod):
    p = tmp_path / 'sentiment_hist.pkl'
    p.write_bytes(b'not-pickle')
    mod._senti_hist_paths = lambda: [str(p)]
    assert mod._senti_hist_load() == 0
    assert mod.g.senti_hist == {}


def test_save_load_roundtrip(tmp_path, mod):
    p = tmp_path / 'sentiment_hist.pkl'
    mod.senti_hist_fp = lambda: str(p)
    mod._senti_hist_paths = lambda: [str(p)]
    mod.g.senti_hist = {'2026-11-02': {'date': '2026-11-02', 'ice': True, 'stage_flags': ['cold']}}
    assert mod._senti_hist_save() == 1
    mod.g.senti_hist = {}
    assert mod._senti_hist_load() == 1
    assert mod.g.senti_hist['2026-11-02']['ice'] is True
