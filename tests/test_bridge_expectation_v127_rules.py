# -*- coding: utf-8 -*-
"""PT 云端离线 bridge 与 AXquant 对齐：bad_seal 三态、负基、一字开盘档位。"""
from research.expectation.bridge.model import (
    ROLE_DETAIL_BAD_SEAL_BOARD,
    ROLE_DETAILS,
)
from research.expectation.bridge.rules import (
    evaluate_auction_status,
    one_word_open_meet_min_pct,
)
from research.expectation.bridge.publish import (
    derive_expectation_weight,
    derive_role_detail,
    derive_sell_policy_hint,
)


def test_bridge_model_accepts_bad_seal_role():
    assert ROLE_DETAIL_BAD_SEAL_BOARD in ROLE_DETAILS


def test_bridge_auction_negative_basis_exceed():
    status, reasons = evaluate_auction_status(
        review={"yesterday_open_pct": -0.93},
        auction_change_pct=1.5,
    )
    assert status == "pending_exceed"
    assert "auction_higher_than_yesterday" in reasons


def test_bridge_auction_missing_basis_keeps_awaiting():
    status, reasons = evaluate_auction_status(review={}, auction_change_pct=2.0)
    assert status == "awaiting_auction"
    assert "missing_yesterday_open" in reasons


def test_bridge_bad_seal_three_states():
    review = {"role_detail": ROLE_DETAIL_BAD_SEAL_BOARD}
    assert evaluate_auction_status(review=review, auction_change_pct=0.5)[0] == "pending_exceed"
    assert evaluate_auction_status(review=review, auction_change_pct=-1.0)[0] == "pending_meet"
    assert evaluate_auction_status(review=review, auction_change_pct=-2.1)[0] == "pending_miss"


def test_bridge_one_word_open_meet_min_pct():
    assert one_word_open_meet_min_pct(10.0) == 8.0
    assert one_word_open_meet_min_pct(20.0) == 16.0
    assert one_word_open_meet_min_pct(30.0) == 24.0


def test_bridge_bad_seal_derived_and_policy():
    review, evidence, derived = derive_role_detail(
        "000001.SZ",
        role="consecutive_limit_up",
        snapshot={
            "open_times": 3,
            "seal_money": 5000000.0,
            "max_seal_money": 120000000.0,
            "continue_day_cnt": 2,
        },
    )
    assert review == ROLE_DETAIL_BAD_SEAL_BOARD
    assert derived is True
    assert "open_times_3" in evidence["decision_reasons"]
    assert derive_sell_policy_hint(review) == "fast_exit_on_weak"
    assert derive_expectation_weight(review, "normal", 50) < 50
