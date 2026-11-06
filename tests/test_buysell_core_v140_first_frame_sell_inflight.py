# -*- coding: utf-8 -*-
"""v1.40 首帧 tx 基准 + 卖出 FILLED 数量级 + 撤单终态口径回归测试。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v140_test", STRATEGY_PATH)
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
    m.get_trading_day = lambda: "2026-11-05"
    m._min_age = lambda: 5
    m._hhmm = lambda: "09:35"
    m.g = SimpleNamespace(
        boards={},
        stock_boards={},
        board_type={},
        zt_lianban={},
        pool_static=[],
        watch=[],
        skip_log_ts={},
        csnap_led=None,
        csnap_last_diag=None,
        first_zt={},
        spot={},
        pending={},
        daily={},
        buy_log={},
        sold_log={},
    )
    return m


def test_board_first_frame_tx_rejects_stale_first_tx(mod):
    # 2026-11-05 001360：真实首笔 09:30:23.660，检测帧 09:30:46，feed_lag=23.13s。
    # tx 基准必须拒绝已封 23s 的票，ts 检测帧基准仍放行（作为对照）。
    mod.g.spot["A.XSHE"] = {"up_px": 10.0}
    mod.last_px = lambda sec: 10.0
    t0 = time.time() - 23.13
    lt = time.localtime(t0)
    ms = str(int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int(t0 % 1 * 1000))
    mod.g.first_zt["A.XSHE"] = {"ms": ms, "ts": time.time(), "src": "tx"}

    assert mod._board_first_frame_ok("A.XSHE", baseline="tx") is False
    assert mod._board_first_frame_ok("A.XSHE", baseline="ts") is True


def test_board_first_frame_tx_falls_back_to_ts(mod):
    # tx_ms 缺失（snap 首触）：tx 基准回退检测帧 ts，兼容无逐笔环境。
    mod.g.spot["A.XSHE"] = {"up_px": 10.0}
    mod.last_px = lambda sec: 10.0
    mod.g.first_zt["A.XSHE"] = {"ts": time.time(), "src": "snap"}

    assert mod._board_first_frame_ok("A.XSHE", baseline="tx") is True


def test_buy_ff_log_marks_firstzt_lag(mod):
    # 首帧门拒绝且 feed_lag 超窗时，[firstzt-lag] 单独留痕，区分供方延迟与策略拒绝。
    t0 = time.time() - 23.13
    lt = time.localtime(t0)
    ms = str(int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int(t0 % 1 * 1000))
    mod.g.first_zt["A.XSHE"] = {"ms": ms, "ts": time.time(), "src": "tx"}

    mod._buy_ff_log("A.XSHE", "expected", "wait")
    assert any("[buy-ff]" in x and "gate=wait" in x and "feed_lag=23.13" in x for x in mod._logs)
    assert any("[firstzt-lag]" in x and "feed_lag=23.13" in x for x in mod._logs)


def _sell_pend(src_qty, filled, status="FILLED"):
    return {"side": "sell", "status": status, "src_qty": src_qty,
            "filled": filled, "ts": time.time()}


def test_sell_inflight_filled_partial_clears_and_allows(mod):
    # 002425 类残留：本次卖单 FILLED 400/800，桥仍有剩余 -> 清理放行后续卖出评估。
    mod.g.pending["A.XSHE"] = _sell_pend(800, 400)
    mod._sell_pos_total = lambda sec, positions: 400
    mod.get_positions = lambda: {"A.XSHE": {"amount": 400}}

    assert mod._sell_inflight("A.XSHE") is False
    assert "A.XSHE" not in mod.g.pending
    assert any("[sell-remain-clear]" in x and "src_qty=800 filled=400" in x for x in mod._logs)


def test_sell_inflight_filled_full_keeps_block(mod):
    # 整票卖完：FILLED 800/800 -> 继续锁死，不重投。
    mod.g.pending["A.XSHE"] = _sell_pend(800, 800)
    mod._sell_pos_total = lambda sec, positions: 0
    mod.get_positions = lambda: {"A.XSHE": {"amount": 0}}

    assert mod._sell_inflight("A.XSHE") is True
    assert "A.XSHE" in mod.g.pending
    assert not any("[sell-remain-clear]" in x for x in mod._logs)


def test_sell_inflight_filled_legacy_no_src_uses_pos_total(mod):
    # 旧状态无 src_qty：桥总量 400 > 0 视为仍有剩余，不得静默锁死。
    mod.g.pending["A.XSHE"] = _sell_pend(0, 400)
    mod._sell_pos_total = lambda sec, positions: 400
    mod.get_positions = lambda: {"A.XSHE": {"amount": 400}}

    assert mod._sell_inflight("A.XSHE") is False
    assert "A.XSHE" not in mod.g.pending


def test_query_open_status_all_final_priority(mod):
    # open 显示在途但 all 已有终态：终态优先，撤单/查询口径统一。
    mod.get_open_orders = lambda: [{"entrust_no": "655001832", "symbol": "A.XSHE",
                                    "side": "1", "amount": 100}]
    mod.get_all_orders = lambda: [{"entrust_no": "655001832", "order_status": "5",
                                   "symbol": "A.XSHE", "side": "1", "amount": 100}]

    assert mod._query_open_order_status("655001832") == "CANCELLED"


def test_query_open_status_sent_when_all_no_final(mod):
    # open 在途且 all 无终态：保持 SENT（001360 场景），交由 cancel_pending 兜底。
    mod.get_open_orders = lambda: [{"entrust_no": "655001832", "symbol": "A.XSHE",
                                    "side": "1", "amount": 100}]
    mod.get_all_orders = lambda: []

    assert mod._query_open_order_status("655001832") == "SENT"


def test_board_queue_cancel_sent_keeps_pending_and_audits(mod):
    # 撤单后查询仍 SENT：保持 cancel_pending 不释放，并打 [cancel-audit] 口径核对。
    mod.g.pending["A.XSHE"] = {
        "side": "buy", "status": "SENT", "no": "655001832", "qty": 100,
        "seal_base": 100.0, "filled": 0, "ts": time.time(),
    }
    mod.g.first_zt["A.XSHE"] = {"break_cnt": 0}
    mod._seal_metrics = lambda sec: (1.0, 1)
    mod._query_open_order_status = lambda ent, sec=None, side=None, qty=None, backfill=False: "SENT"
    mod.cancel_order = lambda ent: None
    mod._buy_commit_rel = lambda *a, **k: None
    mod._release_buy_slot = lambda sec: None
    mod._unique_stand = lambda sec: False

    assert mod._board_queue_cancel("A.XSHE", 1.0, 1) is True
    assert mod.g.pending["A.XSHE"]["cancel_pending"] is True
    assert any("[board-cancel-pending]" in x and "查询=SENT" in x for x in mod._logs)
    assert any("[cancel-audit]" in x and "ent=655001832" in x for x in mod._logs)
