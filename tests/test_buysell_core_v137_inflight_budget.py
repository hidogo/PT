# -*- coding: utf-8 -*-
"""v1.37 exp_file 并发修复 / board-hist1d 优先级与 TTL / 委托在途心跳与重建证据回归测试。"""
import importlib.util
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v137_inflight_test", STRATEGY_PATH)
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
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-05"
    m.g = SimpleNamespace(
        exp_file={},
        spot={},
        auction_c={},
        auction_confirm_log={},
        zt_lianban={},
        one_word_open=set(),
        first_zt={},
        first_zt_rebuild_pending=[],
        first_zt_rebuild_attempts={},
        first_zt_rebuild_retry_ts={},
        first_zt_rebuild_zt_seen={},
        first_zt_rebuild_zt_hit={},
        first_zt_rebuild_gave_up=set(),
        restart_rebuild_hb_ts=0.0,
        hist_na_pending={},
        skip_log_ts={},
        pending={},
        buy_commit={},
        sell_inflight_warn_logged=set(),
        last_no_reply_reconcile_ts=0.0,
        daily=m._new_daily() if hasattr(m, "_new_daily") else {"bought": [], "sold": []},
    )
    return m


def test_exp_file_snapshot_iteration_survives_concurrent_write(mod):
    mod.g.exp_file = {"S%03d" % i: {"side": "buy"} for i in range(30)}
    seen = []

    def mutate():
        time.sleep(0.001)
        for i in range(200):
            mod.g.exp_file["X%03d" % i] = {"side": "buy"}

    t = threading.Thread(target=mutate)
    t.start()
    try:
        for code, _en in list(mod.g.exp_file.items()):
            seen.append(code)
    finally:
        t.join()

    assert len(seen) >= 30


def test_load_expectation_merge_is_atomic_replace(mod, tmp_path):
    fp = tmp_path / "expectation_latest.csv"
    fp.write_text("code,side,entry_type,expected_status,yesterday_open_pct,expected_auction_change_pct,seal_amount_t0,sell_policy_hint,role_detail\n"
                  "A,buy,normal,pending_exceed,1.0,1.0,0,,,\n"
                  "B,buy,normal,pending_meet,0.5,0.5,0,,,\n",
                  encoding="utf-8")
    mod._expectation_paths = lambda: [str(fp)]
    mod.g.exp_file = {"A": {"side": "buy", "expected_status": "pending_meet"},
                      "C": {"side": "buy", "expected_status": "pending_meet"}}
    old = mod.g.exp_file

    mod._load_expectation(merge=True)

    assert mod.g.exp_file is not old          # 原子替换，旧引用不再被原地更新
    assert mod.g.exp_file["A"]["expected_status"] == "pending_exceed"
    assert "B" in mod.g.exp_file
    assert "C" in mod.g.exp_file              # 旧有但新文件缺失保留


def test_synth_pool_expect_merges_atomically(mod):
    mod.g.zt_lianban = {"A": {"board_cnt": 1}, "B": {"board_cnt": 2}}
    mod.g.spot = {
        "A": {"preclose_px": 10.0, "open_px": 10.5},
        "B": {"preclose_px": 10.0, "open_px": 9.9},
    }
    mod.g.exp_file = {"K": {"side": "buy"}}
    mod._get_snapshot_many = lambda codes, cap: dict(mod.g.spot)
    mod._mid_board_avoid = lambda sec: False
    mod._yesterday_open_chg = lambda sec: (1.0, True)
    old = mod.g.exp_file

    mod._synth_pool_expect(src="original_0925")

    assert mod.g.exp_file is not old
    assert "K" in mod.g.exp_file              # 旧条目保留
    assert mod.g.exp_file["A"]["_src"] == "zt_pool"
    assert "B" in mod.g.exp_file


def test_hist1d_core_ttl_long_lived(mod):
    assert mod._hist1d_ttl(1) == float(mod.BLS["hist1d_core_ttl"]) == 600.0


def test_hist_na_pending_add_reports_reason(mod):
    mod._get_ds = lambda: SimpleNamespace(cache={("hist1d", "A"): (time.time() - 9999.0, object())})
    mod._hist_na_pending_add("A")
    assert "reason=ttl_expired" in mod._logs[-1]

    mod._logs[:] = []
    mod._get_ds = lambda: SimpleNamespace(cache={})
    mod._hist_na_pending_add("B")
    assert "reason=lookup_fail" in mod._logs[-1]


def test_board_strength_info_uses_prio_for_hist_priority(mod):
    calls = []
    mod._is_hist_priority = lambda sec: sec == "CORE"
    mod._concept_active = lambda: True
    mod._concept_strong_board = lambda sec: "B1"
    mod._concept_boards_of = lambda sec: ["B1"]
    mod._concept_board_strength_info = lambda board, prio=0: calls.append((board, prio)) or (1.0, True)

    assert mod._board_strength_info("CORE") == (1.0, True)
    assert mod._board_strength_info("OTHER") == (1.0, True)
    assert calls == [("B1", 1), ("B1", 0)]


def test_source_limit_board_prio_fast_and_afternoon(mod):
    mod._min_age = lambda: 5
    assert mod._source_limit("board", 1) == float(mod.BLS["frame_board_prio_limit_fast"])
    mod._min_age = lambda: 60
    mod._hhmm = lambda: "10:15"
    assert mod._source_limit("board", 1) == float(mod.BLS["frame_board_prio_limit_afternoon"])


def test_no_reply_reconcile_emits_inflight_heartbeat(mod):
    mod.BLS["order_no_reply_timeout"] = 30.0
    mod.g.pending = {"A": {"no": "1001", "side": "buy", "qty": 100, "limit": 10.0,
                           "status": "SENT", "ts": time.time() - 120.0,
                           "day": "2026-11-05"}}
    mod._query_open_order_status = lambda ent, sec=None, side=None, qty=None, backfill=False: "SENT"

    assert mod._no_reply_reconcile() == 0
    assert any("[order-inflight]" in x for x in mod._logs)
    assert mod.g.pending["A"]["ts"] > time.time() - 60.0


def test_sell_inflight_stall_warn_and_heartbeat(mod):
    mod.BLS["sell_pending_timeout"] = 30.0
    mod.BLS["sell_inflight_stall_warn_sec"] = 60.0
    mod.g.pending = {"A": {"no": "2001", "side": "sell", "qty": 100,
                           "status": "SENT", "ts": time.time() - 300.0}}
    mod._query_open_order_status = lambda ent, sec=None, side=None, qty=None, backfill=False: "SENT"

    assert mod._sell_inflight("A") is True
    assert any("[sell-inflight-warn]" in x for x in mod._logs)
    assert "A" in mod.g.sell_inflight_warn_logged

    mod._logs[:] = []
    mod._sell_inflight_heartbeat("A", "3s")
    assert any("[sell-inflight-skip]" in x and "in-flight" in x for x in mod._logs)


def test_restart_rebuild_giveup_logs_evidence_fields(mod):
    mod.g.first_zt_rebuild_pending = ["A"]
    mod.g.first_zt_rebuild_attempts = {"A": 8}
    mod.g.first_zt_rebuild_zt_hit = {"A": 2}
    mod.g.spot = {"A": {"up_px": 10.0}}
    mod.g.zt_lianban = {"A": {"board_cnt": 3}}
    mod.g.one_word_open = {"A"}
    mod.last_px = lambda sec: 9.0
    mod._is_st = lambda sec: False

    mod._rebuild_first_zt_tick()

    giveup = [x for x in mod._logs if "放弃(重试8轮" in x]
    assert giveup and "涨停证据未解析" in giveup[0]
    assert "tx_zt_hit=2" in giveup[0]
    assert "one_word=1" in giveup[0]
    assert "zt_cnt=3" in giveup[0]
