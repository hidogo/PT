# -*- coding: utf-8 -*-
"""T 日复盘观点发布与 T+1 预期确认的辅助函数。

这里只做纯逻辑与文件读取；网络行情拉取由脚本层通过 RT-DAL/腾讯回退链完成，
再调用本模块生成 JSONL 记录。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .model import (
    ENTRY_TYPE_NORMAL,
    ENTRY_TYPE_ONE_WORD,
    EXPECTATION_HINTS,
    ExpectationRecord,
    PositionReviewRecord,
    ROLE_CAPACITY_TREND,
    ROLE_CONSECUTIVE_LIMIT_UP,
    ROLE_ELASTIC_ARB,
    ROLE_FIRST_BOARD,
    ROLE_DETAIL_FIRST_BOARD_ARB,
    ROLE_DETAIL_LEADING_FIRST_BOARD,
    ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP,
    ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE,
    ROLE_DETAIL_ELASTIC_ARB,
    ROLE_DETAIL_CAPACITY_ARB,
    ROLE_DETAIL_JUNK_FOLLOWER,
    ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP,
    ROLE_DETAILS,
    ROLES,
    STATUS_AWAITING_AUCTION,
    STATUS_CONFIRMED_EXCEED,
    STATUS_CONFIRMED_MEET,
    STATUS_CONFIRMED_MISS,
)
from .rules import (
    evaluate_auction_status,
    evaluate_intraday_status,
    evaluate_one_word_expectation,
)


LIMIT_UP_REVIEW_GLOB = "limit-up-review-*.md"
DEFAULT_REVIEW_DIR = Path("docs") / "review"
DEFAULT_SNAPSHOT_DIR = Path("data") / "special_snapshots"
DEFAULT_BOARDS_DIR = Path("docs") / "review"
DEFAULT_EXPECTATION_DATA_DIR = Path("data")

CRITICAL_EXPECTATION_FIELDS = {
    "yesterday_open_pct",
    "auction_change_pct",
    "opened_above_yesterday",
    "quote_source",
    "quote_age_sec",
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
        if out != out or out in (float("inf"), float("-inf")):
            return default
        return out
    except (TypeError, ValueError):
        return default


def _first_number(*values: Any) -> float | None:
    """取首个有效数值；空值、布尔与 NaN 视为缺失，0.0 是合法数值。"""
    for value in values:
        if value is None or value == "" or isinstance(value, bool):
            continue
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out == out and out not in (float("inf"), float("-inf")):
            return out
    return None


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _flag(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "", 0, "0", "false", "False"):
        return default
    return bool(value)


def normalize_code(code: str) -> str:
    """统一股票代码为 600000.SH 形式。"""
    code = str(code or "").strip().upper()
    if not code:
        return ""
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix) and len(code) > len(prefix):
            code = code[len(prefix):]
    if "." not in code:
        num = code
        if num.startswith(("4", "8", "920")):
            return f"{num}.BJ"
        if num.startswith(("6", "9")):
            return f"{num}.SH"
        return f"{num}.SZ"
    return code


def previous_trading_date_by_weekday(today: date) -> date:
    """按工作日回退，周末前优先取上一交易日。"""
    prev = today - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def _calendar_cache_dates() -> set[date]:
    """读取 data/tmp/calendar.json 缓存中的交易日，失败/过期时返回空。"""
    cache_path = Path("data") / "tmp" / "calendar.json"
    if not cache_path.is_file():
        return set()
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        item = payload.get("data") or {}
        rows = item.get("item") or []
        out: set[date] = set()
        for row in rows:
            raw = str(row.get("date") or row.get("date_ms") or "")
            try:
                if raw.isdigit() and len(raw) == 8:
                    out.add(date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])))
                elif raw:
                    out.add(date.fromisoformat(raw[:10]))
            except ValueError:
                continue
        return out
    except Exception:
        return set()


def is_trading_day(day: date | str | None = None, force: bool = False) -> bool:
    """保守判断某日是否为 A 股交易日。

    优先依据 data/tmp/calendar.json 缓存；缓存缺失或目标日期晚于缓存时，
    按工作日放宽（避免因过期缓存误伤未来交易日）。
    """
    if force:
        return True
    if day is None:
        d = date.today()
    elif isinstance(day, datetime):
        d = day.date()
    elif isinstance(day, date):
        d = day
    else:
        d = date.fromisoformat(str(day)[:10])
    if d.weekday() >= 5:
        return False
    calendar_days = _calendar_cache_dates()
    if not calendar_days:
        return True
    if d in calendar_days:
        return True
    if d < max(calendar_days):
        return False
    return True


def resolve_review_date(today: date, review_dir: Path | None = None) -> date:
    """取早于 today 的最近交易日。

    优先级：实际复盘/预期 JSONL 文件日期（当日数据优先于可能陈旧的日历缓存）
    -> 交易日历缓存 -> 复盘 MD -> 工作日回退。
    """
    data_dir = Path(
        os.environ.get("PTRADE_EXPECTATION_DATA_DIR") or os.environ.get("AXQUANT_EXPECTATION_DATA_DIR", str(DEFAULT_EXPECTATION_DATA_DIR))
    )
    file_dates: set[date] = set()
    for base in (data_dir, data_dir / "review"):
        try:
            paths = base.glob("position_review_*.jsonl")  # T 日复盘驱动，排除假期 position_expectation 残留
        except OSError:
            continue
        for path in paths:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
            if not match:
                continue
            try:
                file_dates.add(date.fromisoformat(match.group(1)))
            except ValueError:
                continue
    if file_dates:
        prior = [d for d in file_dates if d < today]
        if prior:
            # 排除休市日残留文件（如假期产物），有交易日历时只取真实交易日；日历缺失时回退文件日期。
            cal = _calendar_cache_dates()
            if cal:
                prior = [d for d in prior if d in cal]
                if prior:
                    return max(prior)
            return max(prior)
    calendar_days = _calendar_cache_dates()
    if calendar_days:
        prior = [d for d in calendar_days if d < today]
        if prior:
            return max(prior)
    review_dir = Path(review_dir or DEFAULT_REVIEW_DIR)
    files = sorted(
        review_dir.glob(LIMIT_UP_REVIEW_GLOB),
        key=lambda p: p.name,
        reverse=True,
    )
    for path in files:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        if not match:
            continue
        try:
            review_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if review_date < today:
            return review_date
    return previous_trading_date_by_weekday(today)


def load_snapshot_map(
    trade_date: str,
    data_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """读取 data/special_snapshots/YYYY-MM-DD.json，返回 code -> 涨停池条目。"""
    data_dir = Path(data_dir or DEFAULT_SNAPSHOT_DIR)
    path = data_dir / f"{trade_date}.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key in ("first_board", "consecutive_board", "h100", "board"):
        rows = payload.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = normalize_code(row.get("code") or "")
            if code and code not in out:
                out[code] = row
    return out


def load_break_codes(
    trade_date: str,
    boards_dir: Path | None = None,
) -> set[str]:
    """读取当日看板 JSON 的炸板池与断板池代码集合，供 T+1 预期下修使用。"""
    boards_dir = Path(boards_dir or DEFAULT_BOARDS_DIR)
    path = boards_dir / f"limit_up_boards_{trade_date}.json"
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    codes: set[str] = set()
    for key in ("break_pool", "broken_pool_today"):
        container = payload.get(key) or {}
        rows = container.get("item") or [] if isinstance(container, dict) else container or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = normalize_code(row.get("thscode") or row.get("code") or "")
            if code:
                codes.add(code)
    return codes


def derive_closing_break_status(
    trade_date: str,
    boards_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """读取当日看板 JSON 的断板池与炸板池，输出收盘断板/炸板状态。

    返回 {code: {"break_kind": "broken"|"break", "board_num": int, "is_break": True}}，
    供持仓/苗子复盘重算收盘地位（断板持仓不再沿用买入时地位字段）。
    """
    boards_dir = Path(boards_dir or DEFAULT_BOARDS_DIR)
    path = boards_dir / f"limit_up_boards_{trade_date}.json"
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return out
    for key, kind in (("broken_pool_today", "broken"), ("break_pool", "break")):
        container = payload.get(key) or {}
        rows = container.get("item") or [] if isinstance(container, dict) else container or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = normalize_code(row.get("thscode") or row.get("code") or "")
            if not code:
                continue
            out.setdefault(
                code,
                {
                    "break_kind": kind,
                    "board_num": _int(row.get("board_num"), 0),
                    "is_break": True,
                },
            )
    return out


def load_closing_pool_rows(
    trade_date: str,
    boards_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """读取收盘涨停池条目（看板 JSON pool 优先，special snapshot 兜底）。

    返回统一字段的 dict 列表：code / name / continue_day_cnt / limit_up_time /
    seal_money / limit_up_reason；无数据返回空列表。
    """
    boards_dir = Path(boards_dir or DEFAULT_BOARDS_DIR)
    path = boards_dir / f"limit_up_boards_{trade_date}.json"
    rows: list[dict[str, Any]] = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        pool = payload.get("pool") or {}
        if isinstance(pool, dict):
            items = pool.get("item") or []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    code = normalize_code(
                        item.get("thscode") or item.get("ticker") or item.get("code") or ""
                    )
                    if not code:
                        continue
                    rows.append(
                        {
                            "code": code,
                            "name": str(item.get("name") or ""),
                            "continue_day_cnt": _int(
                                item.get("continue_day_cnt"), 1
                            ),
                            "limit_up_time": str(item.get("limit_up_time") or ""),
                            "seal_money": _float(item.get("seal_money"), 0),
                            "limit_up_reason": str(item.get("limit_up_reason") or ""),
                        }
                    )
    if rows:
        return rows
    # 兜底：special snapshot（首板/连板合并）
    for code, row in load_snapshot_map(trade_date).items():
        rows.append(
            {
                "code": code,
                "name": str(row.get("name") or ""),
                "continue_day_cnt": _int(row.get("continue_day_cnt"), 1),
                "limit_up_time": str(row.get("limit_up_time") or ""),
                "seal_money": _float(
                    row.get("seal_money"), _float(row.get("seal_amount_t0"), 0)
                ),
                "limit_up_reason": str(row.get("limit_up_reason") or ""),
            }
        )
    return rows


_BOARD_MAPPING_CACHE: dict[str, set[str]] | None = None
_BOARD_MAPPING_FILES = (
    Path(__file__).resolve().parents[3] / "data" / "ths_board_mapping.json",
    Path(__file__).resolve().parents[3] / "data" / "board_mapping_from_astock.json",
    # v0.37 兜底 AXquant 同源 THS 概念映射（导出/复盘离线读取, 消除首 token 拆组漂移）
    Path(__file__).resolve().parents[4] / "AXquant" / "data" / "ths_board_mapping.json",
)


def _load_board_mapping() -> dict[str, set[str]]:
    """加载个股→板块映射（code -> set[板块名]），供收盘地位重算归并同链。

    优先 ths_board_mapping.json，兜底 astock 映射；解析失败返回空（调用方
    回退首 token 分组）。文件在 data/ 下，复盘进程可离线读取，避免与 live
    的 DuckDB 写连接冲突。
    """
    global _BOARD_MAPPING_CACHE
    if _BOARD_MAPPING_CACHE is not None:
        return _BOARD_MAPPING_CACHE
    mapping: dict[str, set[str]] = {}
    for path in _BOARD_MAPPING_FILES:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 映射缺失时回退首 token
            continue
        if isinstance(payload, dict):
            for code, boards in payload.items():
                if isinstance(boards, (list, tuple, set)):
                    norm = normalize_code(code)
                    if norm:
                        mapping.setdefault(norm, set()).update(
                            str(b).strip() for b in boards if str(b).strip()
                        )
        elif isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                # v0.37 只消费概念口径（对齐板块消费"只消费概念板块"约定），过滤 industry 行业板块
                if str(item.get("board_type") or "").strip() not in ("", "concept"):
                    continue
                code = normalize_code(
                    item.get("code")
                    or item.get("stock_code")
                    or item.get("symbol")
                    or ""
                )
                board = str(item.get("board_name") or item.get("concept") or "").strip()
                if code and board:
                    mapping.setdefault(code, set()).add(board)
        if mapping:
            break
    _BOARD_MAPPING_CACHE = mapping
    return mapping


_THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("传媒出版", ("出版", "传媒", "影视", "短剧", "漫剧", "视频", "游戏", "图书", "院线", "广电", "文化", "财联社", "发行", "IP", "AIGC", "互动影游")),
    ("电池锂电", ("电池", "锂电", "储能", "钠电", "固态", "电解液", "负极", "正极", "隔膜", "盐湖提锂")),
    ("机器人", ("机器人", "人形", "伺服", "减速器", "自动化", "缝制")),
    ("医药", ("医药", "制药", "创新药", "抗生素", "CRO", "疫苗", "医疗", "生物", "核医药", "减肥药", "医用", "集采")),
    ("数据/AI安全", ("AI安全", "网络安全", "数据安全", "信息安全", "密码", "智算", "数据中心", "算力", "数据要素", "数据确权", "人工智能安全")),
    ("半导体", ("半导体", "芯片", "存储", "光刻", "封测", "晶圆", "电子特气", "功率半导体", "微电子")),
    ("PCB/电子材料", ("PCB", "覆铜板", "MLCC", "电子材料", "电子化学品", "元件", "电容", "硅烷")),
    ("化工/新材料", ("化工", "有机硅", "氟", "磷", "钛", "稀土", "碳纤维", "尼龙", "铬", "锆", "化纤")),
    ("消费/零售/食品", ("零售", "百货", "超市", "食品", "乳业", "白酒", "电商", "商业综合体", "家电", "服装", "消费", "餐饮", "旅游", "文旅", "粮油", "奶酪")),
    ("农业/橡胶/种业", ("种业", "玉米", "橡胶", "粮食", "饲料", "农业", "育种", "米业", "水产", "水产品")),
    ("光伏/风电/电力", ("光伏", "风电", "电网", "绿电", "核电", "氢能", "电力", "储能电站", "玻璃")),
    ("地产/基建", ("房地产", "地产", "物业", "基建", "建筑", "装修", "城投", "设计")),
    ("汽车/汽配", ("汽车", "汽配", "整车", "智能驾驶", "特斯拉", "充电", "轮胎")),
    ("黄金/有色/资源", ("黄金", "有色", "铜", "铝", "矿产", "资源", "金属")),
    ("金融/证券", ("券商", "证券", "金融", "银行", "保险", "信托", "创投", "互联网金融")),
]


def _primary_theme_bucket(reason: str) -> str:
    """按主题关键词返回涨停原因的主桶（首个命中），无命中返回空串。"""
    tokens = [
        t.strip()
        for t in re.split(r"[\s+，、,；;/&|]", reason or "")
        if t.strip()
    ]
    for label, keywords in _THEME_KEYWORDS:
        for tok in tokens:
            if any(k in tok for k in keywords):
                return label
    return ""


def _reason_related_boards(code: str, reason: str) -> set[str]:
    """涨停原因关联板块：映射板块中与 reason token 有子串包含关系的集合。

    同时保留 reason 首 token 兜底（映射缺失或未命中时仍能按原口径归并）。
    """
    mapping = _load_board_mapping()
    tokens = [
        t.strip()
        for t in re.split(r"[\s+、,，/；;]+", reason or "")
        if t.strip()
    ]
    first = tokens[0] if tokens else ""
    bucket = _primary_theme_bucket(reason)
    boards = set(mapping.get(code) or ())
    related: set[str] = set()
    if bucket:
        related.add("桶:" + bucket)
    for b in boards:
        if not b:
            continue
        for t in tokens:
            if t and len(t) >= 2 and (t in b or b in t):
                related.add(b)
                break
    if not related and first:
        related.add(first)
    return related


def _board_sets_overlap(bs: set[str], ot: set[str]) -> bool:
    """两股票板块集合是否共享同一产业链（同名或子串包含即同链）。"""
    # 仅精确匹配：主题桶与板块名精确相同才并组，取消子串匹配避免跨主题误并。
    return bool(bs & ot)


# 题材桶（与 AXquant 复盘 theme.buckets / docs/45 R1 同源）：
# unique_high 分组 = 每股按 limit_up_reason 命中全部题材桶，共享任一题材即并组（连通分量）。
THEME_BUCKETS = [
    (
        "AI/数据要素/算力",
        (
            "AI", "数据", "算力", "人工智能", "大模型", "网络安全", "数据中心",
            "数据库", "智算", "端侧", "Token", "算网", "语料", "语义", "数字政府",
            "数字财税", "数字出版", "数智", "裸眼3D",
        ),
    ),
    (
        "传媒出版/短剧/游戏",
        ("传媒", "出版", "短剧", "影视", "广电", "漫剧", "视频", "游戏", "IP", "文化", "电视", "影院"),
    ),
    (
        "机器人/自动化",
        ("机器人", "人形", "伺服", "减速器", "自动化", "物理AI", "具身", "MEMS", "机械"),
    ),
    ("羊字辈/玄学", ("字辈",)),
    (
        "医药/医疗",
        ("医药", "制药", "医疗", "创新药", "生物", "诊断", "中药", "化学制药", "抗生素", "CRO", "疫苗", "减肥"),
    ),
    (
        "半导体/电子材料",
        ("半导体", "芯片", "存储", "光刻", "封测", "晶圆", "MLCC", "电子", "覆铜板", "电容", "元件"),
    ),
    (
        "汽车/汽配/飞行汽车",
        ("汽车", "汽配", "整车", "智能驾驶", "特斯拉", "充电", "飞行汽车", "增程", "轮胎", "动力"),
    ),
    (
        "消费/零售/食品",
        ("零售", "百货", "超市", "食品", "乳业", "白酒", "电商", "家电", "服装", "消费", "餐饮", "旅游", "粮油", "调味", "菌株", "益生菌"),
    ),
    (
        "农业/养殖",
        ("养殖", "种业", "饲料", "粮食", "农业", "水产", "海参", "生猪", "鱼粉", "橡胶", "玉米", "米业"),
    ),
    (
        "光伏/风电/电力/储能",
        ("光伏", "风电", "电网", "绿电", "核电", "氢能", "电力", "储能", "电池", "锂电", "钠电", "电解液", "负极", "正极", "隔膜"),
    ),
    (
        "地产/基建",
        ("房地产", "地产", "物业", "基建", "建筑", "装修", "城投", "水泥", "设计"),
    ),
    (
        "金融/证券",
        ("券商", "证券", "金融", "银行", "保险", "信托", "创投", "互联网金融"),
    ),
    (
        "黄金/有色/资源",
        ("黄金", "有色", "铜", "铝", "矿产", "资源", "金属", "锆", "铬", "钛", "稀土"),
    ),
    (
        "化工/新材料",
        ("化工", "有机硅", "氟", "磷", "碳纤维", "尼龙", "化纤", "骨架材料", "热熔胶", "胶"),
    ),
]


def _split_reason_tokens(reason):
    text = (
        str(reason or "")
        .replace(u"\u201c", "")
        .replace(u"\u201d", "")
        .replace('"', "")
        .replace("'", "")
    )
    return [t.strip() for t in re.split(r"[\s+、，,；;/&|·]+", text) if t.strip()]


def _theme_tags_of(reason):
    """涨停原因命中的全部题材桶（themes 全量，与云端 _zt_themes_of 同源）。"""
    tags = set()
    for label, keywords in THEME_BUCKETS:
        for tok in _split_reason_tokens(reason):
            if any(k in tok for k in keywords):
                tags.add(label)
                break
    return tags


def derive_closing_board_status(
    trade_date: str,
    boards_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """收盘地位重算：按收盘涨停池重建板块最高身位/唯一性/跟风数/板块排名。

    板块口径与复盘 board_name 一致（limit_up_reason 首 token 拆分）；
    仅当同板块（同首 token）至少 2 家时才判定唯一性/跟风，避免把伪板块
    单票误标为唯一龙头；board_rank 优先用 board_rank 模块补齐，缺失保持 0。
    返回 {code: {board_name, board_rank, unique_high_board,
                 follower_count, follower_codes, closing_pool_height}}。
    """
    rows = load_closing_pool_rows(trade_date, boards_dir)
    n = len(rows)
    if n == 0:
        return {}
    # 题材归并（docs/45 R1）：每股按 themes 全量（全部命中题材桶）并组，
    # 以题材为节点、共享成员即连通，避免主因分组造成伪唯一（如 600094 案例）。
    themes_by_idx = [
        _theme_tags_of(str(r.get("limit_up_reason") or "")) for r in rows
    ]
    parent = list(range(n))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if themes_by_idx[i] & themes_by_idx[j]:
                _union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)

    code_heights: dict[str, int] = {}
    for idxs in groups.values():
        for item in (rows[i] for i in idxs):
            try:
                code_heights[str(item.get("code") or "")] = max(
                    1, int(_int(str(item.get("continue_day_cnt") or "1"), 1))
                )
            except (TypeError, ValueError):
                code_heights[str(item.get("code") or "")] = 1
    global_max_height = max(code_heights.values(), default=1)
    global_top_codes = {c for c, h in code_heights.items() if h == global_max_height}

    out: dict[str, dict[str, Any]] = {}
    for idxs in groups.values():
        items = [rows[i] for i in idxs]
        try:
            heights = [
                max(1, int(_int(str(item.get("continue_day_cnt") or "1"), 1)))
                for item in items
            ]
        except (TypeError, ValueError):
            continue
        max_h = max(heights)
        top = [item for item, h in zip(items, heights) if h == max_h]
        # 组内至少 2 家、且最高身位唯一才授予唯一身位。
        unique = len(top) == 1 and (
            len(items) >= 2
            or (
                max_h == global_max_height
                and len(global_top_codes) == 1
                and str(top[0].get("code") or "") in global_top_codes
            )
        )
        leader = top[0] if unique else None
        board = ""
        if leader:
            reason = str(leader.get("limit_up_reason") or "")
            board = re.split(r"[\s+、,，/；;]+", reason, maxsplit=1)[0].strip()
            board = board.strip("“”\"'（）()")
        rank = None
        if board:
            try:
                rank = None  # 离线独立运行：无 AXquant board_rank 数据源
            except Exception:
                rank = None
        leader_code = str(leader["code"]) if leader else ""
        for item, h in zip(items, heights):
            code = str(item.get("code") or "")
            is_leader = unique and code == leader_code
            followers = (
                sorted(
                    other["code"]
                    for other, oh in zip(items, heights)
                    if str(other.get("code") or "") != code and oh < h
                )
                if is_leader
                else []
            )
            out[code] = {
                "board_name": board,
                "board_rank": rank,
                "unique_high_board": is_leader,
                "follower_count": len(followers),
                "follower_codes": followers,
                "closing_pool_height": h,
            }
    return out


MAX_SEEDLING_REVIEW_CODES = 24


def derive_seedling_codes(
    trade_date: str,
    closing_board_status: dict[str, dict[str, Any]] | None = None,
    insights: dict[str, Any] | None = None,
    held_codes: set[str] | None = None,
    boards_dir: Path | None = None,
) -> list[str]:
    """核心苗子候选代码：收盘唯一身位龙头 + 早封大封单 + 复盘超预期交集。

    排除风险代码与已持仓代码（持仓走 holding 复盘）；
    排序优先复盘核心 > 板块唯一龙头 > 早封/封单强度，上限 MAX_SEEDLING_REVIEW_CODES。
    """
    insights = insights or {}
    closing_board_status = closing_board_status or {}
    risk_codes = {
        normalize_code(str(c))
        for c in insights.get("risk_codes") or []
        if str(c).strip()
    }
    surprise_codes = {
        normalize_code(str(c))
        for c in (
            insights.get("core_seedling_codes")
            or insights.get("surprise_codes")
            or []
        )
        if str(c).strip()
    }
    rows = {r["code"]: r for r in load_closing_pool_rows(trade_date, boards_dir)}
    pool_codes = set(closing_board_status) or set(rows)
    priority: dict[str, float] = {}
    for code in surprise_codes & pool_codes:
        priority[code] = max(priority.get(code, 0.0), 100.0)
    for code, status in closing_board_status.items():
        if status.get("unique_high_board") and int(status.get("follower_count") or 0) >= 1:
            priority[code] = max(priority.get(code, 0.0), 60.0)
    for code in pool_codes:
        row = rows.get(code) or {}
        limit_up_time = str(row.get("limit_up_time") or "")
        seal = _float(row.get("seal_money"), 0)
        if limit_up_time and limit_up_time <= "09:35" and seal >= 3e7:
            priority[code] = max(priority.get(code, 0.0), 40.0)
    excluded = risk_codes | set(held_codes or ())
    selected = [
        code
        for code in sorted(
            priority,
            key=lambda c: (
                -priority[c],
                -_float(rows.get(c, {}).get("seal_money"), 0),
                c,
            ),
        )
        if code not in excluded
    ]
    return selected[:MAX_SEEDLING_REVIEW_CODES]


def seedling_open_reasons(
    trade_date: str,
    codes: Iterable[str],
    closing_board_status: dict[str, dict[str, Any]] | None = None,
    boards_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """把核心苗子代码合成轻量开仓理由，供 make_review_records 生成候选地位复盘。"""
    closing_board_status = closing_board_status or {}
    rows = {r["code"]: r for r in load_closing_pool_rows(trade_date, boards_dir)}
    out: list[dict[str, Any]] = []
    for code in codes:
        row = rows.get(code) or {}
        if not row:
            continue
        closing = closing_board_status.get(code) or {}
        reason = str(row.get("limit_up_reason") or "")
        board_name = str(
            closing.get("board_name")
            or reason.split("+", 1)[0].strip()
            or ""
        )
        height = _int(row.get("continue_day_cnt"), 1)
        if height >= 2:
            role = ROLE_CONSECUTIVE_LIMIT_UP
        elif str(code).startswith(("300", "301", "688", "689")):
            role = ROLE_ELASTIC_ARB
        else:
            role = ROLE_FIRST_BOARD
        limit_up_time = str(row.get("limit_up_time") or "")
        entry_type = (
            ENTRY_TYPE_ONE_WORD
            if "一字" in str(row.get("continue_day_text") or "")
            or limit_up_time.startswith("09:25")
            else ENTRY_TYPE_NORMAL
        )
        out.append(
            {
                "code": code,
                "name": str(row.get("name") or ""),
                "scenario": "core_seedling",
                "role": role,
                "entry_type": entry_type,
                "limit_up_time": limit_up_time,
                "seal_amount_t0": _float(row.get("seal_money"), 0),
                "board_name": board_name,
                "unique_high_board": bool(closing.get("unique_high_board")),
                "follower_count": int(closing.get("follower_count") or 0),
                "follower_codes": list(closing.get("follower_codes") or []),
                "review_kind": "seedling",
                "source_agent": "core_seedling",
            }
        )
    return out


def derive_role(
    code: str,
    reason: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> str:
    reason = reason or {}
    snapshot = snapshot or {}
    role = str(reason.get("role") or "")
    if role in ROLES:
        return role
    limit_up_count = _int(snapshot.get("continue_day_cnt"), _int(reason.get("limit_up_count"), 0))
    if limit_up_count >= 2:
        return ROLE_CONSECUTIVE_LIMIT_UP
    if code[:3] in ("300", "301", "688", "689"):
        return ROLE_ELASTIC_ARB
    if reason.get("scenario") in ("elastic_arb", "capacity_trend"):
        return ROLE_CAPACITY_TREND if reason.get("scenario") == "capacity_trend" else ROLE_ELASTIC_ARB
    return ROLE_FIRST_BOARD


def _role_detail_evidence(
    snapshot: dict[str, Any] | None = None,
    reason: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = snapshot or {}
    reason = reason or {}
    reasons: list[str] = []
    if _flag(snapshot.get("unique_high_board"), _flag(reason.get("unique_high_board"), False)):
        reasons.append("unique_high_board")
    board_rank = _int(snapshot.get("board_rank"), _int(reason.get("board_rank"), 0))
    if board_rank > 0:
        reasons.append(f"board_rank_{board_rank}")
    limit_up_time = str(snapshot.get("limit_up_time") or reason.get("limit_up_time") or "")
    if limit_up_time:
        reasons.append(f"limit_up_time_{limit_up_time}")
    seal_amount_t0 = _float(snapshot.get("seal_money"), _float(reason.get("seal_amount_t0"), 0))
    if seal_amount_t0 > 0:
        reasons.append(f"seal_amount_t0_{seal_amount_t0:.0f}")
    follower_count = _int(snapshot.get("follower_count"), _int(reason.get("follower_count"), 0))
    if follower_count > 0:
        reasons.append(f"follower_count_{follower_count}")
    return {
        "decision_reasons": reasons,
        "role_detail_sample": {
            "board_rank": board_rank,
            "limit_up_time": limit_up_time,
            "seal_amount_t0": seal_amount_t0,
            "unique_high_board": _flag(
                snapshot.get("unique_high_board"), _flag(reason.get("unique_high_board"), False)
            ),
            "follower_count": follower_count,
        },
    }


def _junk_follower_evidence(
    snapshot: dict[str, Any] | None = None,
    reason: dict[str, Any] | None = None,
) -> str:
    """识别杂毛跟风：非涨停或绿盘，且不具备强势地位证据。"""
    snapshot = snapshot or {}
    reason = reason or {}
    change_pct = snapshot.get("change_pct", snapshot.get("daily_change", reason.get("change_pct")))
    if change_pct not in (None, ""):
        try:
            if float(change_pct) < 0:
                return "green_close"
        except (TypeError, ValueError):
            pass
    price = snapshot.get("price", reason.get("price"))
    limit_up = snapshot.get("limit_up", snapshot.get("limit_up_price", reason.get("limit_up")))
    if price not in (None, "") and limit_up not in (None, ""):
        try:
            if float(price) < float(limit_up) * 0.995:
                return "not_limit_up"
        except (TypeError, ValueError):
            pass
    if reason.get("is_limit_up") is False or snapshot.get("is_limit_up") is False:
        if price not in (None, ""):
            return "not_limit_up"
    return ""


def derive_role_detail(
    code: str,
    role: str | None = None,
    reason: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], bool]:
    """推导当日地位细分类（role_detail）。

    优先使用显式传入的 role_detail；否则按旧 role + 涨停池证据推导。
    """
    reason = reason or {}
    snapshot = snapshot or {}
    explicit = str(reason.get("role_detail") or snapshot.get("role_detail") or "")
    if explicit in ROLE_DETAILS:
        return explicit, _role_detail_evidence(snapshot, reason), False
    junk_evidence = _junk_follower_evidence(snapshot, reason)
    if junk_evidence:
        evidence = _role_detail_evidence(snapshot, reason)
        if "green_close" not in evidence["decision_reasons"]:
            evidence["decision_reasons"].append(junk_evidence)
        return ROLE_DETAIL_JUNK_FOLLOWER, evidence, True
    if str(snapshot.get("break_kind") or "") == "broken":
        return ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP, _role_detail_evidence(snapshot, reason), True
    role = role or derive_role(code, reason, snapshot)
    if role == ROLE_FIRST_BOARD:
        unique = _flag(snapshot.get("unique_high_board"), _flag(reason.get("unique_high_board"), False))
        board_rank = _int(snapshot.get("board_rank"), _int(reason.get("board_rank"), 0))
        limit_up_time = str(snapshot.get("limit_up_time") or reason.get("limit_up_time") or "")
        seal_amount_t0 = _float(snapshot.get("seal_money"), _float(reason.get("seal_amount_t0"), 0))
        leading = unique or board_rank in (1, 2) or (
            bool(limit_up_time) and limit_up_time <= "09:40" and seal_amount_t0 >= 3e7
        )
        detail = ROLE_DETAIL_LEADING_FIRST_BOARD if leading else ROLE_DETAIL_FIRST_BOARD_ARB
    elif role == ROLE_CONSECUTIVE_LIMIT_UP:
        unique = _flag(snapshot.get("unique_high_board"), _flag(reason.get("unique_high_board"), False))
        detail = ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE if unique else ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP
    elif role == ROLE_ELASTIC_ARB:
        detail = ROLE_DETAIL_ELASTIC_ARB
    elif role == ROLE_CAPACITY_TREND:
        detail = ROLE_DETAIL_CAPACITY_ARB
    else:
        detail = ""
    return detail, _role_detail_evidence(snapshot, reason), True


def derive_expectation_weight(
    role_detail: str,
    entry_type: str | None = None,
    strength: float = 50.0,
) -> float:
    """由当日地位给次日预期一个基础权重，后续供 AGENT/看板做软参考。"""
    base = {
        ROLE_DETAIL_LEADING_FIRST_BOARD: 65.0,
        ROLE_DETAIL_FIRST_BOARD_ARB: 42.0,
        ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP: 55.0,
        ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE: 72.0,
        ROLE_DETAIL_ELASTIC_ARB: 50.0,
        ROLE_DETAIL_CAPACITY_ARB: 58.0,
        ROLE_DETAIL_JUNK_FOLLOWER: 30.0,
        ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP: 35.0,
    }.get(role_detail, 50.0)
    if entry_type == ENTRY_TYPE_ONE_WORD:
        base += 8.0
    return max(0.0, min(100.0, (base + max(0.0, _float(strength) - 50.0) * 0.2)))


def derive_sell_policy_hint(role_detail: str) -> str:
    """根据当日地位给卖出策略一个倾向提示，实际卖出由买卖树具体分支执行。"""
    if role_detail in (
        ROLE_DETAIL_LEADING_FIRST_BOARD,
        ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE,
    ):
        return "hold_higher_tolerance"
    if role_detail == ROLE_DETAIL_FIRST_BOARD_ARB:
        return "fast_exit_on_weak"
    if role_detail == ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP:
        return "watch_break_sell"
    if role_detail in (ROLE_DETAIL_ELASTIC_ARB, ROLE_DETAIL_CAPACITY_ARB):
        return "vwap_follow"
    if role_detail == ROLE_DETAIL_JUNK_FOLLOWER:
        return "fast_exit_on_weak"
    if role_detail == ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP:
        return "break_weak_escape"
    return "none"


T1_EXPECTATION_LABELS = {
    "exceed": "超预期走强",
    "meet": "符合预期分歧",
    "miss": "不及预期走弱",
}

# 收盘角色/地位 -> (exceed, meet, miss) 基础三态概率。
T1_BASE_PROBABILITY = {
    ROLE_DETAIL_LEADING_FIRST_BOARD: (0.42, 0.40, 0.18),
    ROLE_DETAIL_FIRST_BOARD_ARB: (0.30, 0.42, 0.28),
    ROLE_DETAIL_MID_CONSECUTIVE_LIMIT_UP: (0.34, 0.42, 0.24),
    ROLE_DETAIL_UNIQUE_HIGH_BOARD_CONSECUTIVE: (0.48, 0.34, 0.18),
    ROLE_DETAIL_ELASTIC_ARB: (0.38, 0.36, 0.26),
    ROLE_DETAIL_CAPACITY_ARB: (0.40, 0.40, 0.20),
    ROLE_DETAIL_JUNK_FOLLOWER: (0.18, 0.34, 0.48),
    ROLE_DETAIL_BROKEN_CONSECUTIVE_LIMIT_UP: (0.16, 0.34, 0.50),
}
T1_DEFAULT_PROBABILITY = (0.32, 0.40, 0.28)


def derive_t1_expectation(
    role_detail: str,
    entry_type: str = ENTRY_TYPE_NORMAL,
    strength: float = 50.0,
    limit_up_time: str = "",
    seal_amount_t0: float = 0.0,
    is_break: bool = False,
) -> dict[str, Any]:
    """按 T 日收盘角色/地位生成 T+1 日预期三态。

    三态统一为 exceed（超预期走强）/ meet（符合预期分歧）/ miss（不及预期
    走弱），与次日确认逻辑的 confirmed_* 语义一致；炸板标的按“炸板+地位”
    下修，把主导概率向 miss 迁移。
    """
    base = T1_BASE_PROBABILITY.get(role_detail, T1_DEFAULT_PROBABILITY)
    e, m, s = float(base[0]), float(base[1]), float(base[2])

    if entry_type == ENTRY_TYPE_ONE_WORD:
        e += 0.06
        s -= 0.06
    if str(limit_up_time or "") and str(limit_up_time) <= "09:35":
        e += 0.04
        s -= 0.04
    seal = _float(seal_amount_t0, 0.0)
    if seal >= 1e8:
        e += 0.06
        s -= 0.06
    elif seal >= 3e7:
        e += 0.03
        s -= 0.03
    strength = _float(strength, 50.0)
    if strength >= 80:
        e += 0.04
        s -= 0.04
    elif strength <= 40:
        e -= 0.04
        s += 0.04

    if is_break:
        e -= 0.22
        s += 0.26

    e = max(0.04, min(0.85, e))
    m = max(0.04, min(0.85, m))
    s = max(0.04, min(0.85, s))
    total = e + m + s
    e, m, s = e / total, m / total, s / total

    ranked = sorted(
        [("exceed", e), ("meet", m), ("miss", s)],
        key=lambda item: -item[1],
    )
    primary, secondary = ranked[0][0], ranked[1][0]
    basis_parts = [
        str(role_detail or "未分类"),
        "今日炸板" if is_break else "收盘封板",
    ]
    if str(limit_up_time or ""):
        basis_parts.append(f"{limit_up_time}封板")
    if seal > 0:
        basis_parts.append(f"封单{seal / 1e4:.0f}万")
    return {
        "three_states": [
            {
                "state": "exceed",
                "label": T1_EXPECTATION_LABELS["exceed"],
                "probability": round(e, 3),
            },
            {
                "state": "meet",
                "label": T1_EXPECTATION_LABELS["meet"],
                "probability": round(m, 3),
            },
            {
                "state": "miss",
                "label": T1_EXPECTATION_LABELS["miss"],
                "probability": round(s, 3),
            },
        ],
        "primary": primary,
        "secondary": secondary,
        "is_break": bool(is_break),
        "basis": "，".join(part for part in basis_parts if part),
    }


def derive_strength(
    snapshot: dict[str, Any] | None = None,
    reason: dict[str, Any] | None = None,
) -> float:
    """用封单/早封时间给当日观点一个 0-100 强度的粗判值。"""
    snapshot = snapshot or {}
    reason = reason or {}
    seal = _float(snapshot.get("seal_money"), _float(reason.get("seal_amount_t0"), 0))
    max_seal = _float(snapshot.get("max_seal_money"), 0)
    limit_up_time = str(snapshot.get("limit_up_time") or reason.get("limit_up_time") or "")
    strength = 50.0
    if seal > 0:
        if seal >= 2e8:
            strength = 85.0
        elif seal >= 1e8:
            strength = 80.0
        elif seal >= 5e7:
            strength = 72.0
        elif seal >= 1e7:
            strength = 66.0
        else:
            strength = 60.0
    if max_seal >= 3e8:
        strength += 5.0
    if limit_up_time:
        if limit_up_time <= "09:35":
            strength += 10.0
        elif limit_up_time <= "10:00":
            strength += 5.0
    return max(0.0, min(100.0, strength))


def make_review_records(
    trade_date: str,
    open_reasons: Iterable[dict[str, Any]],
    snapshot_map: dict[str, dict[str, Any]] | None = None,
    review_insights: dict[str, Any] | None = None,
    break_codes: set[str] | None = None,
    closing_board_status: dict[str, dict[str, Any]] | None = None,
    break_status: dict[str, dict[str, Any]] | None = None,
) -> list[PositionReviewRecord]:
    """从 T 日开仓理由与涨停池快照生成 T 日 AGENT 复盘观点。"""
    snapshot_map = snapshot_map or {}
    insights = review_insights or {}
    break_codes = set(break_codes or set())
    closing_board_status = closing_board_status or {}
    break_status = break_status or {}
    surprise_codes = set(str(x) for x in (insights.get("surprise_codes") or []))
    risk_codes = set(str(x) for x in (insights.get("risk_codes") or []))
    seen: set[str] = set()
    out: list[PositionReviewRecord] = []
    for raw in open_reasons:
        if not isinstance(raw, dict):
            continue
        code = normalize_code(raw.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        snap = snapshot_map.get(code) or {}
        closing = closing_board_status.get(code) or {}
        snap2 = dict(snap)
        for field in (
            "unique_high_board",
            "follower_count",
            "follower_codes",
            "board_rank",
            "board_name",
        ):
            if closing.get(field) is not None:
                snap2.setdefault(field, closing[field])
        bk = break_status.get(code) or {}
        is_broken = str(bk.get("break_kind") or "") == "broken"
        if is_broken:
            snap2["break_kind"] = "broken"
            snap2["seal_money"] = 0
            snap2["limit_up_time"] = ""
            snap2["unique_high_board"] = False
            snap2["follower_count"] = 0
            snap2["follower_codes"] = []
            snap2["board_rank"] = None
            snap2["continue_day_cnt"] = max(2, _int(bk.get("board_num"), 2))
        role = derive_role(code, raw, snap2)
        if is_broken:
            role = ROLE_CONSECUTIVE_LIMIT_UP
        role_detail, board_role_evidence, role_detail_derived = derive_role_detail(
            code, role, raw, snap2
        )
        is_break = code in break_codes
        entry_type = str(raw.get("entry_type") or ENTRY_TYPE_NORMAL)
        if entry_type != ENTRY_TYPE_ONE_WORD and (
            "一字" in str(snap2.get("continue_day_text") or "")
            or "一字" in str(raw.get("reason") or "")
        ):
            entry_type = ENTRY_TYPE_ONE_WORD
        seal_amount_t0 = _float(snap2.get("seal_money"), _float(raw.get("seal_amount_t0"), 0))
        board_name = str(raw.get("board_name") or "")
        if not board_name:
            board_name = str(snap2.get("board_name") or "")
        if not board_name and snap2.get("limit_up_reason"):
            board_name = str(snap2["limit_up_reason"]).split("+", 1)[0].strip()
        strength = derive_strength(snap2, raw)
        auction_change_pct = raw.get("auction_change_pct")
        if auction_change_pct is None:
            auction_change_pct = snap2.get("auction_change_pct")
        opened_above_yesterday = raw.get("opened_above_yesterday")
        if opened_above_yesterday is None:
            opened_above_yesterday = snap2.get("opened_above_yesterday")
        quote_source = str(raw.get("quote_source") or snap2.get("quote_source") or "").strip()
        quote_age_sec = raw.get("quote_age_sec")
        if quote_age_sec is None:
            quote_age_sec = snap2.get("quote_age_sec")
        yesterday_open_pct = _first_number(
            raw.get("yesterday_open_pct"),
            snap2.get("yesterday_open_pct"),
        )
        board_boost = _float(raw.get("board_boost"), _float(snap2.get("board_boost"), 0))
        if board_boost <= 0 and board_name:
            try:
                board_boost = 0.0  # 离线独立运行：无 AXquant board_rank 数据源
            except Exception:
                board_boost = 0.0
        if (
            opened_above_yesterday is None
            and isinstance(auction_change_pct, (int, float))
            and not isinstance(auction_change_pct, bool)
            and yesterday_open_pct is not None
        ):
            opened_above_yesterday = float(auction_change_pct) > yesterday_open_pct
        evidence_reasons = list(board_role_evidence.get("decision_reasons") or [])
        critical_missing = [
            name
            for name, value in {
                "yesterday_open_pct": yesterday_open_pct,
                "auction_change_pct": auction_change_pct,
                "opened_above_yesterday": opened_above_yesterday,
            }.items()
            if value is None or value == ""
        ]
        missing_fields = [
            name
            for name, value in {
                "yesterday_open_pct": yesterday_open_pct,
                "auction_change_pct": auction_change_pct,
                "opened_above_yesterday": opened_above_yesterday,
                "quote_age_sec": quote_age_sec,
                "quote_source": quote_source,
                "role_detail": role_detail,
                "board_role_evidence": "board_role_evidence" if evidence_reasons else "",
            }.items()
            if value is None or value == ""
        ]
        input_incomplete = bool(critical_missing)
        if str(raw.get("source_agent") or "") == "position_fallback":
            # 真实持仓兜底缺少开仓理由/地位证据，即使补齐竞价数值也不应生成“可判预期”复盘。
            # missing_fields 只保留真实缺失字段，避免把已回填的竞价数值误标为缺失。
            input_incomplete = True
            if not missing_fields:
                missing_fields.append("review_input_incomplete")
        if not input_incomplete:
            if code in surprise_codes:
                expectation_hint = "likely_exceed"
            elif code in risk_codes:
                expectation_hint = "likely_miss"
            else:
                expectation_hint = "likely_meet"
        else:
            expectation_hint = "unclear"
        expectation_weight = derive_expectation_weight(role_detail, entry_type, strength)
        sell_policy_hint = derive_sell_policy_hint(role_detail)
        t1_expectation = derive_t1_expectation(
            role_detail=role_detail,
            entry_type=entry_type,
            strength=strength,
            limit_up_time=str(snap2.get("limit_up_time") or raw.get("limit_up_time") or ""),
            seal_amount_t0=seal_amount_t0,
            is_break=is_break,
        )
        role_label = role_detail or role or "unclassified"
        board_rank_value: int | None = None
        if not is_broken:
            board_rank_value = snap2.get("board_rank")
            if closing and "board_rank" not in snap2:
                board_rank_value = closing.get("board_rank")
            if board_rank_value is None and not closing:
                board_rank_value = raw.get("board_rank")
        try:
            board_rank_value = (
                int(float(board_rank_value)) if board_rank_value is not None else None
            )
        except (TypeError, ValueError):
            board_rank_value = None
        review_conclusion = (
            f"{role_label} 强度{strength:.0f} 封单{seal_amount_t0:.0f} "
            f"板块{board_name or '-'}，首日观点由 AGENT 自动生成"
        )
        out.append(
            PositionReviewRecord(
                trade_date=trade_date,
                code=code,
                name=str(raw.get("name") or snap2.get("name") or ""),
                review_kind=str(raw.get("review_kind") or "holding"),
                role=role,
                role_detail=role_detail,
                junk_follower=(role_detail == ROLE_DETAIL_JUNK_FOLLOWER),
                entry_type=entry_type,
                strength=round(strength, 2),
                limit_up_time=str(snap2.get("limit_up_time") or raw.get("limit_up_time") or ""),
                seal_amount_t0=round(seal_amount_t0, 2),
                seal_quality=str(snap2.get("seal_pct") or snap2.get("seal_quality") or ""),
                follower_count=_int(snap2.get("follower_count"), _int(raw.get("follower_count"), 0)),
                follower_codes=list(
                    snap2.get("follower_codes") or raw.get("follower_codes") or []
                ),
                unique_high_board=_flag(
                    snap2.get("unique_high_board"), _flag(raw.get("unique_high_board"), False)
                ),
                board_name=board_name,
                board_rank=board_rank_value,
                board_boost=round(board_boost, 2),
                yesterday_open_pct=yesterday_open_pct,
                auction_change_pct=auction_change_pct,
                opened_above_yesterday=opened_above_yesterday,
                quote_source=quote_source,
                quote_age_sec=quote_age_sec,
                expectation_hint=expectation_hint if expectation_hint in EXPECTATION_HINTS else "unclear",
                review_conclusion=review_conclusion,
                source_agent=str(raw.get("source_agent") or "recommend_agent"),
                created_at=datetime.now().isoformat(timespec="milliseconds"),
                review_input_incomplete=input_incomplete,
                missing_fields=missing_fields,
                board_role_evidence=board_role_evidence,
                expectation_weight=round(expectation_weight, 2),
                sell_policy_hint=sell_policy_hint,
                role_detail_derived=role_detail_derived,
                t1_expectation=t1_expectation,
            )
        )
    return out


def _quote_dict(quote: Any) -> dict[str, Any]:
    if hasattr(quote, "to_dict"):
        return quote.to_dict()
    if isinstance(quote, dict):
        return quote
    return {}


def _normalize_ts(value: float) -> float:
    """行情时间戳统一为秒；毫秒值自动归一化，避免 stale 判断反向。"""
    if value > 1e12:
        value = value / 1000.0
    return value


def _quote_fields(quote: Any) -> tuple[float, float, float, float, float, float, int, float, list, float, str]:
    q = _quote_dict(quote)
    price = _float(q.get("price", q.get("lastPrice")), 0)
    open_price = _float(q.get("open"), 0)
    high = _float(q.get("high"), 0)
    low = _float(q.get("low"), 0)
    last_close = _float(q.get("last_close", q.get("lastClose")), 0)
    limit_up = _float(q.get("limit_up", q.get("limitUp")), 0)
    volume = _int(q.get("volume"), 0)
    amount = _float(q.get("amount"), 0)
    bid_volume = _int((q.get("bid_vol") or [0])[0], 0)
    quote_ts = _normalize_ts(_float(q.get("quote_ts"), time.time()))
    quote_source = str(q.get("quote_source") or "")
    return (price, open_price, high, low, last_close, limit_up, volume, amount, [bid_volume], quote_ts, quote_source)


def _quote_has_ts(quote: Any) -> bool:
    if quote is None:
        return False
    q = _quote_dict(quote)
    raw = q.get("quote_ts", q.get("lastTime", q.get("timestamp", q.get("ts", ""))))
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False


def _quote_age_ok(quote: Any, max_age: float) -> bool:
    """行情新鲜度判断：缺少时间戳视为不可信，避免用旧快照置换成预期三态。"""
    if max_age <= 0:
        return True
    if not _quote_has_ts(quote):
        return False
    q = _quote_dict(quote)
    ts = _normalize_ts(
        _float(q.get("quote_ts", q.get("lastTime", q.get("timestamp", q.get("ts", 0)))), 0)
    )
    return ts > 0 and time.time() - ts <= max_age


def _input_incomplete_review(review: dict[str, Any]) -> list[str]:
    """返回复盘记录中会导致预期判定失真的关键缺失字段。"""
    missing = [
        str(x)
        for x in (review.get("missing_fields") or [])
        if x in CRITICAL_EXPECTATION_FIELDS
    ]
    if review.get("review_input_incomplete"):
        return missing or ["review_input_incomplete"]
    return missing


def confirm_auction(
    reviews: Iterable[dict[str, Any]],
    quotes: dict[str, Any],
    cfg: dict[str, Any] | None = None,
    trade_date: str | None = None,
) -> list[ExpectationRecord]:
    """用 T+1 集合竞价快照生成首批预期确认结果。"""
    cfg = cfg or {}
    max_quote_age = _float(cfg.get("max_quote_age"), 6.0)
    out: list[ExpectationRecord] = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        code = normalize_code(review.get("code") or "")
        if not code:
            continue
        role_detail_raw = str(review.get("role_detail") or "")
        if role_detail_raw not in ROLE_DETAILS:
            role_detail_raw, _, _ = derive_role_detail(
                code, str(review.get("role") or ""), review
            )
        sell_policy_hint = str(review.get("sell_policy_hint") or "") or derive_sell_policy_hint(role_detail_raw)
        quote = quotes.get(code)
        q = _quote_fields(quote) if quote is not None else (0.0,) * 9 + (0.0, "")
        price, open_price, high, low, last_close, limit_up, volume, amount, bid_vol_list, quote_ts, quote_source = q
        bid_volume = bid_vol_list[0] if bid_vol_list else 0
        max_age = float(max_quote_age or 0)
        stale_quote = quote is None or not _quote_age_ok(quote, max_age)
        incomplete = _input_incomplete_review(review)
        qdict = _quote_dict(quote)
        auction_change_pct = None
        raw_auction_pct = qdict.get("auction_change_pct") if quote is not None else None
        if (
            raw_auction_pct is not None
            and not isinstance(raw_auction_pct, bool)
            and raw_auction_pct not in ("", None)
        ):
            try:
                auction_change_pct = float(raw_auction_pct)
            except (TypeError, ValueError):
                auction_change_pct = None
        if auction_change_pct is None and open_price > 0 and last_close > 0:
            auction_change_pct = round((open_price - last_close) / last_close * 100, 2)
        # 复盘档案的 auction_change_pct 是 T 日开盘涨幅，即 T+1 的“昨日竞价基准”；
        # Agent 合成记录用 yesterday_open_pct 承载同一基准，按来源回退，避免错位一天
        raw_review_open = review.get("auction_change_pct")
        if raw_review_open is None:
            raw_review_open = review.get("yesterday_open_pct")
        review_open_pct = _first_number(raw_review_open)
        opened_above_yesterday = None
        raw_opened_above = qdict.get("opened_above_yesterday") if quote is not None else None
        review_opened_above = review.get("opened_above_yesterday")
        # 仅 Agent 当天合成的记录（synthetic_source / agent_recommendations）才直接
        # 采用其 opened_above_yesterday；复盘档案（含 core_seedling）的该字段是
        # T vs T-1 历史结论，不能作为 T+1 判定，否则重新生成复盘时会误用
        synthetic_today = (
            str(review.get("synthetic_source") or "") == "agent_recommendation"
            or str(review.get("source_agent") or "") == "agent_recommendations"
        )
        if synthetic_today and isinstance(review_opened_above, bool):
            opened_above_yesterday = review_opened_above
        elif isinstance(raw_opened_above, bool) and auction_change_pct is None:
            opened_above_yesterday = raw_opened_above
        elif auction_change_pct is not None and review_open_pct is not None:
            opened_above_yesterday = auction_change_pct > review_open_pct
        runtime_supplied = (
            auction_change_pct is not None
            and opened_above_yesterday is not None
            and bool(quote_source)
            and _quote_has_ts(quote)
        )
        if runtime_supplied:
            incomplete = []
        auction_source = (
            "quote"
            if raw_auction_pct not in (None, "")
            else ("open_calc" if open_price > 0 and last_close > 0 else None)
        )
        entry_type = str(review.get("entry_type") or ENTRY_TYPE_NORMAL)
        reasons: list[str] = []
        status = STATUS_AWAITING_AUCTION
        auction_status = ""
        is_one_word_t1 = None
        seal_amount_t1 = 0.0
        if stale_quote:
            status = STATUS_AWAITING_AUCTION
            reasons = ["stale_quote"]
        elif price <= 0 and open_price <= 0:
            status = STATUS_AWAITING_AUCTION
            reasons = ["missing_quote"]
        elif incomplete or (entry_type == ENTRY_TYPE_ONE_WORD and _float(review.get("seal_amount_t0"), 0) <= 0):
            status = STATUS_AWAITING_AUCTION
            reasons = ["missing_presupposition"]
        elif entry_type == ENTRY_TYPE_ONE_WORD:
            is_one_word_t1 = bool(
                open_price > 0
                and limit_up > 0
                and abs(open_price - limit_up) < 0.01
                and bid_volume > 0
            )
            seal_amount_t1 = float(bid_volume if is_one_word_t1 else 0)
            status, reasons = evaluate_one_word_expectation(
                seal_amount_t0=_float(review.get("seal_amount_t0"), 0),
                seal_amount_t1=seal_amount_t1,
                is_one_word_t1=bool(is_one_word_t1),
            )
            auction_status = status
        else:
            status, reasons = evaluate_auction_status(
                review=review,
                auction_change_pct=auction_change_pct,
                opened_above_yesterday=opened_above_yesterday,
            )
            auction_status = status
        extra = {
            "quote_source": quote_source,
            "quote_ts": quote_ts,
            "quote_age_sec": round(max(0.0, time.time() - quote_ts), 2) if quote_ts > 0 else None,
            "auction_price": open_price,
            "auction_source": auction_source,
            "review_trade_date": review.get("trade_date"),
            "input_incomplete": incomplete or None,
            "review_input_incomplete": incomplete or None,
            "stale_quote": stale_quote or None,
            "board_role_evidence": review.get("board_role_evidence") or {},
            "expectation_weight": review.get("expectation_weight"),
            "role_detail_derived": review.get("role_detail_derived"),
        }
        out.append(
            ExpectationRecord(
                trade_date=trade_date or "",
                code=code,
                review_date=str(review.get("trade_date") or ""),
                role=str(review.get("role") or ""),
                role_detail=role_detail_raw,
                junk_follower=(role_detail_raw == ROLE_DETAIL_JUNK_FOLLOWER),
                sell_policy_hint=sell_policy_hint,
                entry_type=entry_type,
                status=status,
                auction_status=auction_status,
                intraday_status="",
                auction_change_pct=round(auction_change_pct, 2) if auction_change_pct is not None else None,
                opened_above_yesterday=opened_above_yesterday,
                is_one_word_t1=is_one_word_t1,
                seal_amount_t1=round(seal_amount_t1, 2),
                below_vwap=None,
                two_1m_break_above_open=None,
                reasons=reasons,
                updated_at=datetime.now().isoformat(timespec="milliseconds"),
                extra=extra,
            )
        )
    return out


@dataclass
class IntradayState:
    """一个标的在 T+1 盘中确认窗口内的增量状态。"""

    code: str = ""
    prev_daily_change: float | None = None
    one_word_saw_limit_up: bool = False
    one_word_opened_after_open: bool = False
    below_vwap: bool = False
    red_to_green: bool = False
    two_1m_break_above_open: bool = False
    limit_up_within_1m: bool = False
    limit_up_within_1m_at: float = 0.0
    limit_up_price: float = 0.0
    limit_up_within_1m_quote_source: str = ""
    limit_up_within_1m_minute_bar_ts: float = 0.0
    minute_bars: dict[int, dict[str, float]] = field(default_factory=dict)


def _vwap(quote: Any) -> float:
    q = _quote_dict(quote)
    volume = _int(q.get("volume"), 0)
    amount = _float(q.get("amount"), 0)
    if volume <= 0 or amount <= 0:
        return 0.0
    return amount / 100.0 / volume


def _open_minute_bucket(quote_ts: float) -> int:
    """行情时间戳所在交易日的 09:30 开盘分钟桶（本地时间），失败返回 -1。"""
    try:
        local = datetime.fromtimestamp(float(quote_ts))
        open_ts = local.replace(hour=9, minute=30, second=0, microsecond=0).timestamp()
        return int(open_ts // 60)
    except (OSError, OverflowError, ValueError, TypeError):
        return -1


def update_intraday_state(
    state: IntradayState,
    review: dict[str, Any],
    quote: Any,
    cfg: dict[str, Any] | None = None,
) -> None:
    """用新行情快照更新盘中状态；不改状态之外的持久化文件。"""
    cfg = cfg or {}
    q = _quote_dict(quote)
    price = _float(q.get("price"), 0)
    high = _float(q.get("high"), 0)
    low = _float(q.get("low"), 0)
    open_price = _float(q.get("open"), 0)
    limit_up = _float(q.get("limit_up"), 0)
    daily_change = _float(q.get("daily_change"), 0)
    quote_ts = _normalize_ts(_float(q.get("quote_ts"), time.time()))
    if price <= 0:
        return
    if high > 0:
        state.one_word_saw_limit_up = state.one_word_saw_limit_up or (
            limit_up > 0 and high >= limit_up - 0.005
        )
    if str(review.get("entry_type") or "") == ENTRY_TYPE_ONE_WORD:
        if limit_up > 0 and price < limit_up - 0.005 and state.one_word_saw_limit_up:
            state.one_word_opened_after_open = True
        if high > 0 and limit_up > 0 and high > limit_up + 0.005:
            state.one_word_opened_after_open = True
    vwap = _vwap(q)
    # B2：VWAP 必须在当日 low-high 区间（无区间时用价格带校验），异常值不参与判定
    if vwap > 0:
        _vwap_ok = False
        if low > 0 and high > 0:
            _vwap_ok = low <= vwap <= high
        elif price > 0:
            _vwap_ok = 0.5 * price <= vwap <= 2.0 * price
        if _vwap_ok:
            state.below_vwap = price < vwap
    if state.prev_daily_change is not None and state.prev_daily_change > 0 and daily_change < 0:
        state.red_to_green = True
    state.prev_daily_change = daily_change
    minute_key = int(quote_ts // 60)
    bar = state.minute_bars.setdefault(
        minute_key, {"high": price, "last": price, "open": open_price}
    )
    bar["high"] = max(_float(bar.get("high")), price, high)
    bar["last"] = price
    # B2：仅开盘首桶（09:30/09:31）且是首个观测桶才判“1m 内冲涨停”，
    # 晚启动（如 11:29 首帧涨停价）不得误判。
    _open_bucket = _open_minute_bucket(quote_ts)
    if (
        limit_up > 0
        and len(state.minute_bars) <= 1
        and _open_bucket > 0
        and minute_key in (_open_bucket, _open_bucket + 1)
        and (high > 0 or price > 0)
        and max(_float(bar.get("high")), price, high) >= limit_up * 0.995
    ):
        state.limit_up_within_1m = True
        if not state.limit_up_within_1m_at:
            state.limit_up_within_1m_at = quote_ts
            state.limit_up_price = limit_up
            state.limit_up_within_1m_quote_source = str(q.get("quote_source") or "")
            state.limit_up_within_1m_minute_bar_ts = quote_ts
    # 快速上攻：最近 2 根分钟级柱都曾站上开盘价 1% 以上。
    ratio = _float(cfg.get("fast_up_ratio"), 0.01)
    threshold = open_price * (1 + ratio) if open_price > 0 else 0
    keys = sorted(state.minute_bars.keys())
    qualifying = []
    for key in keys:
        b = state.minute_bars[key]
        if threshold > 0 and (b.get("last", 0) >= threshold or b.get("high", 0) >= threshold):
            qualifying.append(key)
    if len(qualifying) >= 2 and keys and keys[-1] in qualifying:
        state.two_1m_break_above_open = True


def confirm_intraday(
    reviews: Iterable[dict[str, Any]],
    quotes: dict[str, Any],
    auction_status_map: dict[str, dict[str, Any]] | None = None,
    states: dict[str, IntradayState] | None = None,
    cfg: dict[str, Any] | None = None,
    trade_date: str | None = None,
) -> list[ExpectationRecord]:
    """盘中确认：读取最新行情，覆盖同一标的的预期记录。"""
    auction_status_map = auction_status_map or {}
    states = states if states is not None else {}
    cfg = cfg or {}
    max_quote_age = _float(cfg.get("max_quote_age"), 6.0)
    out: list[ExpectationRecord] = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        code = normalize_code(review.get("code") or "")
        if not code:
            continue
        role_detail_raw = str(review.get("role_detail") or "")
        if role_detail_raw not in ROLE_DETAILS:
            role_detail_raw, _, _ = derive_role_detail(
                code, str(review.get("role") or ""), review
            )
        sell_policy_hint = str(review.get("sell_policy_hint") or "") or derive_sell_policy_hint(role_detail_raw)
        quote = quotes.get(code)
        if quote is None:
            latest_missing = (auction_status_map.get(code) or {})
            prev_extra = dict(latest_missing.get("extra") or {})
            prev_extra["review_trade_date"] = review.get("trade_date")
            prev_extra["kept_previous_status"] = True
            prev_extra["review_input_incomplete"] = bool(_input_incomplete_review(review))
            prev_reasons = list(latest_missing.get("reasons") or [])
            missing_reasons = [*prev_reasons, "missing_quote"] if prev_reasons else ["missing_quote"]
            out.append(
                ExpectationRecord(
                    trade_date=trade_date or "",
                    code=code,
                    review_date=str(review.get("trade_date") or ""),
                    role=str(review.get("role") or ""),
                    role_detail=role_detail_raw,
                    junk_follower=(role_detail_raw == ROLE_DETAIL_JUNK_FOLLOWER),
                    sell_policy_hint=sell_policy_hint,
                    entry_type=str(review.get("entry_type") or ENTRY_TYPE_NORMAL),
                    status=STATUS_AWAITING_AUCTION,
                    auction_status=str(latest_missing.get("auction_status") or ""),
                    intraday_status="missing_quote_keep_previous",
                    auction_change_pct=latest_missing.get(
                        "auction_change_pct", review.get("auction_change_pct")
                    ),
                    opened_above_yesterday=latest_missing.get(
                        "opened_above_yesterday", review.get("opened_above_yesterday")
                    ),
                    limit_up_within_1m=latest_missing.get("limit_up_within_1m"),
                    below_vwap=latest_missing.get("below_vwap"),
                    two_1m_break_above_open=latest_missing.get(
                        "two_1m_break_above_open"
                    ),
                    reasons=missing_reasons,
                    extra=prev_extra,
                )
            )
            continue
        if not _quote_age_ok(quote, float(max_quote_age or 0)):
            latest_stale = (auction_status_map.get(code) or {})
            prev_extra = dict(latest_stale.get("extra") or {})
            prev_extra["review_trade_date"] = review.get("trade_date")
            prev_extra["kept_previous_status"] = True
            prev_extra["review_input_incomplete"] = bool(_input_incomplete_review(review))
            _stale_q = _quote_dict(quote)
            _stale_raw_ts = _float(
                _stale_q.get("quote_ts", _stale_q.get("lastTime", _stale_q.get("timestamp", _stale_q.get("ts", 0)))),
                0,
            )
            prev_extra["quote_source"] = str(_stale_q.get("quote_source") or "")
            if _stale_raw_ts > 0:
                prev_extra["quote_age_sec"] = round(
                    max(0.0, time.time() - _normalize_ts(_stale_raw_ts)), 2
                )
            prev_reasons = list(latest_stale.get("reasons") or [])
            stale_reasons = [*prev_reasons, "stale_quote"] if prev_reasons else ["stale_quote"]
            out.append(
                ExpectationRecord(
                    trade_date=trade_date or "",
                    code=code,
                    review_date=str(review.get("trade_date") or ""),
                    role=str(review.get("role") or ""),
                    role_detail=role_detail_raw,
                    junk_follower=(role_detail_raw == ROLE_DETAIL_JUNK_FOLLOWER),
                    sell_policy_hint=sell_policy_hint,
                    entry_type=str(review.get("entry_type") or ENTRY_TYPE_NORMAL),
                    status=STATUS_AWAITING_AUCTION,
                    auction_status=str(latest_stale.get("auction_status") or ""),
                    intraday_status="stale_quote_keep_previous",
                    auction_change_pct=latest_stale.get(
                        "auction_change_pct", review.get("auction_change_pct")
                    ),
                    opened_above_yesterday=latest_stale.get(
                        "opened_above_yesterday", review.get("opened_above_yesterday")
                    ),
                    limit_up_within_1m=latest_stale.get("limit_up_within_1m"),
                    below_vwap=latest_stale.get("below_vwap"),
                    two_1m_break_above_open=latest_stale.get(
                        "two_1m_break_above_open"
                    ),
                    reasons=stale_reasons,
                    extra=prev_extra,
                )
            )
            continue
        state = states.setdefault(code, IntradayState(code=code))
        update_intraday_state(state, review, quote, cfg)
        q = _quote_dict(quote)
        price = _float(q.get("price"), 0)
        limit_up = _float(q.get("limit_up"), 0)
        daily_change = _float(q.get("daily_change"), 0)
        latest = auction_status_map.get(code) or {}
        auction_status = str(latest.get("auction_status") or latest.get("status") or "")
        entry_type = str(review.get("entry_type") or ENTRY_TYPE_NORMAL)
        incomplete = _input_incomplete_review(review)
        auction_change_pct = latest.get("auction_change_pct", review.get("auction_change_pct"))
        if auction_change_pct in (None, ""):
            open_price = _float(q.get("open"), 0)
            last_close = _float(q.get("last_close", q.get("lastClose")), 0)
            if open_price > 0 and last_close > 0:
                auction_change_pct = round((open_price - last_close) / last_close * 100, 2)
        opened_above_yesterday = latest.get(
            "opened_above_yesterday", review.get("opened_above_yesterday")
        )
        if opened_above_yesterday is None and auction_change_pct is not None:
            raw_review_open = review.get("auction_change_pct")
            if raw_review_open is None:
                raw_review_open = review.get("yesterday_open_pct")
            review_open_pct = _first_number(raw_review_open)
            if review_open_pct is not None:
                opened_above_yesterday = float(auction_change_pct) > review_open_pct
        runtime_supplied = (
            auction_change_pct is not None
            and opened_above_yesterday is not None
            and bool(q.get("quote_source"))
            and _quote_has_ts(quote)
        )
        if runtime_supplied:
            incomplete = []
        if runtime_supplied and (
            not auction_status or auction_status == STATUS_AWAITING_AUCTION
        ):
            _derived_status, _derived_reasons = evaluate_auction_status(
                review=review,
                auction_change_pct=auction_change_pct,
                opened_above_yesterday=opened_above_yesterday,
            )
            if _derived_status != STATUS_AWAITING_AUCTION:
                auction_status = _derived_status
        auction_source = (
            "auction_map"
            if latest.get("auction_change_pct") is not None
            else ("runtime_quote" if auction_change_pct is not None else None)
        )
        reasons: list[str] = []
        is_one_word_t1 = None
        seal_amount_t1 = 0.0
        status = ""
        if entry_type == ENTRY_TYPE_ONE_WORD:
            is_one_word_t1 = bool(
                limit_up > 0 and price > 0 and abs(price - limit_up) < 0.005
            )
            bid_vol = q.get("bid_vol") or []
            seal_amount_t1 = _float(bid_vol[0] if bid_vol else 0, 0)
            if state.one_word_opened_after_open:
                status, reasons = STATUS_CONFIRMED_MISS, ["one_word_opened_after_open"]
            else:
                status, reasons = evaluate_one_word_expectation(
                    seal_amount_t0=_float(review.get("seal_amount_t0"), 0),
                    seal_amount_t1=seal_amount_t1,
                    is_one_word_t1=bool(is_one_word_t1),
                )
        else:
            if state.limit_up_within_1m:
                status, reasons = STATUS_CONFIRMED_EXCEED, ["limit_up_within_1m"]
            else:
                status, reasons = evaluate_intraday_status(
                    auction_status=auction_status,
                    below_vwap=state.below_vwap,
                    two_1m_break_above_open=state.two_1m_break_above_open,
                    red_to_green=state.red_to_green,
                )
        if incomplete and status != STATUS_CONFIRMED_EXCEED:
            status = STATUS_AWAITING_AUCTION
            auction_status = ""
            reasons = ["missing_presupposition"]
        extra = {
            "quote_source": str(q.get("quote_source") or ""),
            "quote_ts": _normalize_ts(_float(q.get("quote_ts"), time.time())),
            "quote_age_sec": (
                round(
                    max(
                        0.0,
                        time.time() - _normalize_ts(_float(q.get("quote_ts"), time.time())),
                    ),
                    2,
                )
                if _float(q.get("quote_ts"), 0) > 0
                else None
            ),
            "price": price,
            "daily_change": daily_change,
            "vwap": _vwap(q),
            "auction_source": auction_source,
            "review_trade_date": review.get("trade_date"),
            "input_incomplete": incomplete or None,
            "review_input_incomplete": incomplete or None,
            "kept_previous_status": False,
            "limit_up_within_1m": state.limit_up_within_1m,
            "limit_up_within_1m_at": state.limit_up_within_1m_at or None,
            "limit_up_price": state.limit_up_price or None,
            "limit_up_within_1m_quote_source": state.limit_up_within_1m_quote_source or None,
            "limit_up_within_1m_minute_bar_ts": state.limit_up_within_1m_minute_bar_ts or None,
            "board_role_evidence": review.get("board_role_evidence") or {},
            "expectation_weight": review.get("expectation_weight"),
            "role_detail_derived": review.get("role_detail_derived"),
        }
        out.append(
            ExpectationRecord(
                trade_date=trade_date or "",
                code=code,
                review_date=str(review.get("trade_date") or ""),
                role=str(review.get("role") or ""),
                role_detail=role_detail_raw,
                junk_follower=(role_detail_raw == ROLE_DETAIL_JUNK_FOLLOWER),
                sell_policy_hint=sell_policy_hint,
                entry_type=entry_type,
                status=status,
                auction_status=auction_status,
                intraday_status=status,
                auction_change_pct=auction_change_pct,
                opened_above_yesterday=opened_above_yesterday,
                is_one_word_t1=is_one_word_t1,
                seal_amount_t1=round(seal_amount_t1, 2),
                below_vwap=state.below_vwap,
                two_1m_break_above_open=state.two_1m_break_above_open,
                limit_up_within_1m=state.limit_up_within_1m,
                reasons=reasons,
                updated_at=datetime.now().isoformat(timespec="milliseconds"),
                extra=extra,
            )
        )
    return out
