"""次日三态确认规则。"""

from __future__ import annotations

from typing import Any

from .model import (
    ENTRY_TYPE_ONE_WORD,
    ROLE_DETAIL_BAD_SEAL_BOARD,
    ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP,
    STATUS_AWAITING_AUCTION,
    STATUS_PENDING_EXCEED,
    STATUS_PENDING_MEET,
    STATUS_PENDING_MISS,
    STATUS_CONFIRMED_EXCEED,
    STATUS_CONFIRMED_MEET,
    STATUS_CONFIRMED_MISS,
)


def _as_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_bad_seal_role(review: dict[str, Any] | None) -> bool:
    """放量烂板 / 炸板不回封：次日竞价三态用独立档位。"""
    rd = str((review or {}).get("role_detail") or "")
    return rd in (ROLE_DETAIL_BAD_SEAL_BOARD, ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP)


def one_word_open_meet_min_pct(board_limit_pct: float = 10.0) -> float:
    """一字/近一字开盘符合预期下限（主板 +8%，20cm +16%，30cm +24%）。"""
    return max(1.0, float(board_limit_pct) * 0.8)


def evaluate_one_word_expectation(
    seal_amount_t0: float,
    seal_amount_t1: float,
    is_one_word_t1: bool,
) -> tuple[str, list[str]]:
    """T 日一字板标的：次日一字且封单量判断预期。"""
    if not is_one_word_t1:
        return STATUS_CONFIRMED_MISS, ["non_one_word_after_t0_one_word"]
    t0 = _as_float(seal_amount_t0, 0.0)
    t1 = _as_float(seal_amount_t1, 0.0)
    if t0 > 0 and t1 >= t0 * 1.20:
        return STATUS_CONFIRMED_EXCEED, ["one_word_seal_increase_over_20pct"]
    return STATUS_CONFIRMED_MEET, ["one_word_seal_within_20pct"]


def evaluate_one_word_opened_after_open(
    status: str,
    opened_after_open: bool | None,
) -> tuple[str | None, list[str]]:
    """一字板中间开板即降级。"""
    if opened_after_open:
        return STATUS_CONFIRMED_MISS, ["one_word_opened_after_open"]
    return None, []


def evaluate_auction_status(
    review: dict[str, Any] | None = None,
    auction_change_pct: float | None = None,
    opened_above_yesterday: bool | None = None,
) -> tuple[str, list[str]]:
    """普通标的的竞价预期。一字板由 evaluate_one_word_expectation 单独处理。"""
    entry_type = (review or {}).get("entry_type")
    if entry_type == ENTRY_TYPE_ONE_WORD:
        return STATUS_AWAITING_AUCTION, ["one_word_board_requires_seal_rule"]

    raw_yesterday_open = (review or {}).get("yesterday_open_pct")
    has_yesterday_open = raw_yesterday_open is not None
    yesterday_open_pct = _as_float(raw_yesterday_open, 0.0)
    reasons: list[str] = []

    if auction_change_pct is None:
        return STATUS_AWAITING_AUCTION, ["missing_auction_change"]

    # 放量烂板 / 炸板不回封：红开=超预期；-2%<小绿开<=0=符合；<=-2% 或跌停开=低于。
    if _is_bad_seal_role(review):
        if auction_change_pct > 0:
            reasons.append("bad_seal_red_open_exceed")
            return STATUS_PENDING_EXCEED, reasons
        if auction_change_pct <= -2.0:
            reasons.append("bad_seal_big_green_miss")
            return STATUS_PENDING_MISS, reasons
        reasons.append("bad_seal_small_green_meet")
        return STATUS_PENDING_MEET, reasons

    if opened_above_yesterday is True:
        reasons.append("opened_above_yesterday")
        return STATUS_PENDING_EXCEED, reasons
    if opened_above_yesterday is False:
        reasons.append("not_above_yesterday")
        if auction_change_pct < 0:
            reasons.append("auction_green_open")
            return STATUS_PENDING_MISS, reasons
        return STATUS_PENDING_MEET, reasons
    if auction_change_pct < 0:
        reasons.append("auction_green_open")
        return STATUS_PENDING_MISS, reasons
    if has_yesterday_open and auction_change_pct > yesterday_open_pct:
        reasons.append("auction_higher_than_yesterday")
        return STATUS_PENDING_EXCEED, reasons
    if not has_yesterday_open:
        reasons.append("missing_yesterday_open")
        return STATUS_AWAITING_AUCTION, reasons
    reasons.append("auction_small_open")
    return STATUS_PENDING_MEET, reasons


def evaluate_intraday_status(
    auction_status: str,
    below_vwap: bool | None = None,
    two_1m_break_above_open: bool | None = None,
    red_to_green: bool | None = None,
) -> tuple[str, list[str]]:
    """盘中确认：快速上攻 / 不破 VWAP / 破 VWAP 反绿。"""
    reasons: list[str] = []

    if auction_status in (STATUS_PENDING_MISS, STATUS_CONFIRMED_MISS):
        reasons.append("already_miss_from_auction")
        return STATUS_CONFIRMED_MISS, reasons
    if not auction_status or auction_status == STATUS_AWAITING_AUCTION:
        # 没有可用的竞价依据时保持待竞价，不能仅凭“不破 VWAP”判为符合。
        reasons.append("missing_auction_basis")
        return STATUS_AWAITING_AUCTION, reasons
    if two_1m_break_above_open and auction_status in (
        STATUS_PENDING_EXCEED,
        STATUS_CONFIRMED_EXCEED,
    ):
        reasons.append("two_1m_break_above_open_1pct")
        return STATUS_CONFIRMED_EXCEED, reasons
    if below_vwap or red_to_green:
        reasons.append("break_vwap_or_red_to_green")
        return STATUS_CONFIRMED_MISS, reasons
    reasons.append("held_vwap")
    return STATUS_CONFIRMED_MEET, reasons
