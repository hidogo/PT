"""开仓理由 / 当日复盘观点 / 次日预期记录模型。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


ROLE_FIRST_BOARD = "first_board"
ROLE_CONSECUTIVE_LIMIT_UP = "consecutive_limit_up"
ROLE_ELASTIC_ARB = "elastic_arb"
ROLE_CAPACITY_TREND = "capacity_trend"
ROLES = {
    ROLE_FIRST_BOARD,
    ROLE_CONSECUTIVE_LIMIT_UP,
    ROLE_ELASTIC_ARB,
    ROLE_CAPACITY_TREND,
}

# 角色细分（地位细分）：同一角色下按板块地位、身位与弹性进一步区分，
# 用于复盘→次日预期三态的细分标签。
ROLE_DETAIL_LEADING_FIRST_BOARD = "leading_first_board"
ROLE_DETAIL_FIRST_BOARD_ARB = "first_board_arb"
ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP = "mid_consecutive_limit_up"
ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE = "unique_high_board_consecutive"
ROLE_DETAIL_ELASTIC_ARB = "elastic_arb"
ROLE_DETAIL_CAPACITY_ARB = "capacity_arb"
ROLE_DETAIL_JUNK_FOLLOWER = "junk_follower"
ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP = "broken_consecutive_limit_up"
# 所有合法角色细分值集合，供复盘/预期校验使用。
ROLE_DETAILS = {
    ROLE_DETAIL_LEADING_FIRST_BOARD,
    ROLE_DETAIL_FIRST_BOARD_ARB,
    ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP,
    ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE,
    ROLE_DETAIL_ELASTIC_ARB,
    ROLE_DETAIL_CAPACITY_ARB,
    ROLE_DETAIL_JUNK_FOLLOWER,
    ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP,
}

ENTRY_TYPE_NORMAL = "normal"
ENTRY_TYPE_ONE_WORD = "one_word_board"
ENTRY_TYPES = {ENTRY_TYPE_NORMAL, ENTRY_TYPE_ONE_WORD}

EXPECTATION_HINTS = {
    "unclear",
    "likely_exceed",
    "likely_meet",
    "likely_miss",
}

STATUS_AWAITING_AUCTION = "awaiting_auction"
STATUS_PENDING_EXCEED = "pending_exceed"
STATUS_PENDING_MEET = "pending_meet"
STATUS_PENDING_MISS = "pending_miss"
STATUS_CONFIRMED_EXCEED = "confirmed_exceed"
STATUS_CONFIRMED_MEET = "confirmed_meet"
STATUS_CONFIRMED_MISS = "confirmed_miss"
STATUS_DEGRADED = "degraded"


def _pick(value, default: Any = None) -> Any:
    if value is None:
        return default
    return value


@dataclass
class OpenReasonRecord:
    """T 日买入信号/成交的结构化开仓理由。"""

    trade_date: str
    code: str
    scenario: str
    price: float = 0.0
    volume: int = 0
    status: str = "submitted"
    order_id: str = ""
    role: str = ""
    role_detail: str = ""
    entry_type: str = ENTRY_TYPE_NORMAL
    limit_up_time: str = ""
    seal_amount_t0: float = 0.0
    unique_high_board: bool = False
    follower_count: int = 0
    follower_codes: list[str] = field(default_factory=list)
    board_name: str = ""
    board_rank: int = 0
    board_boost: float = 0.0
    yesterday_open_pct: float = 0.0
    auction_change_pct: float | None = None
    opened_above_yesterday: bool | None = None
    buff_id: str = ""
    score_detail: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    quote_source: str = ""
    quote_age_sec: float | None = None
    is_initial_open: bool = True
    ts: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PositionReviewRecord:
    """AGENT 每日复盘生成的持仓当日观点。"""

    trade_date: str
    code: str
    name: str = ""
    review_kind: str = "holding"  # holding=持仓复盘 / seedling=核心苗子候选
    role: str = ""
    role_detail: str = ""
    junk_follower: bool = False
    entry_type: str = ENTRY_TYPE_NORMAL
    strength: float = 0.0
    limit_up_time: str = ""
    seal_amount_t0: float = 0.0
    seal_quality: str = ""
    follower_count: int = 0
    follower_codes: list[str] = field(default_factory=list)
    unique_high_board: bool = False
    board_name: str = ""
    board_rank: int | None = None
    board_boost: float = 0.0
    yesterday_open_pct: float = 0.0
    auction_change_pct: float | None = None
    opened_above_yesterday: bool | None = None
    quote_source: str = ""
    quote_age_sec: float | None = None
    expectation_hint: str = "unclear"
    review_conclusion: str = ""
    source_agent: str = ""
    created_at: str = ""
    review_input_incomplete: bool = False
    missing_fields: list[str] = field(default_factory=list)
    board_role_evidence: dict[str, Any] = field(default_factory=dict)
    expectation_weight: float = 50.0
    sell_policy_hint: str = "none"
    role_detail_derived: bool = False
    t1_expectation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExpectationRecord:
    """T + 1 日预期确认结果。"""

    trade_date: str
    code: str
    review_date: str = ""
    role: str = ""
    role_detail: str = ""
    junk_follower: bool = False
    sell_policy_hint: str = "none"
    entry_type: str = ENTRY_TYPE_NORMAL
    status: str = STATUS_AWAITING_AUCTION
    auction_status: str = ""
    intraday_status: str = ""
    auction_change_pct: float | None = None
    opened_above_yesterday: bool | None = None
    is_one_word_t1: bool | None = None
    seal_amount_t1: float = 0.0
    below_vwap: bool | None = None
    two_1m_break_above_open: bool | None = None
    limit_up_within_1m: bool | None = None
    reasons: list[str] = field(default_factory=list)
    updated_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
