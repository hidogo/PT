"""JSONL 存取层：开仓理由、复盘观点、预期确认结果。"""

from __future__ import annotations

import json
import os
import csv
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

try:
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - non-Windows
    msvcrt = None  # type: ignore


def _expectation_data_dir() -> str:
    """开仓理由/复盘/预期 JSONL 的根目录（独立运行用）。"""
    override = os.environ.get("PTRADE_EXPECTATION_DATA_DIR", "").strip()
    if override:
        return override
    _here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(_here, "..", "..", "..", "data"))


def open_shared_read(path, encoding="utf-8", errors=None):
    """独立运行：本地共享读的简化实现。"""
    return open(path, "r", encoding=encoding, errors=errors)


def replace_file_retry(src, dst, max_attempts=5, base_sleep=0.2):
    """独立运行：原子替换目标文件，句柄占用时退避重试。"""
    for attempt in range(max(1, int(max_attempts))):
        try:
            os.replace(src, dst)
            return True
        except PermissionError:
            time.sleep(float(base_sleep) * (attempt + 1))
        except OSError as exc:
            if getattr(exc, "winerror", None) == 5:
                time.sleep(float(base_sleep) * (attempt + 1))
                continue
            raise
    return False

from .model import (
    OpenReasonRecord,
    PositionReviewRecord,
    ExpectationRecord,
)


_write_lock = threading.Lock()


def _default_data_dir() -> str:
    return _expectation_data_dir()


def default_open_reason_path(trade_date: str | None = None) -> str:
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(_default_data_dir(), "buys", f"open_reason_{trade_date}.jsonl")


def default_expectation_path(trade_date: str | None = None) -> str:
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(_default_data_dir(), f"position_expectation_{trade_date}.jsonl")


def default_review_path(trade_date: str | None = None) -> str:
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(_default_data_dir(), "review", f"position_review_{trade_date}.jsonl")


def build_open_reason_fallback_key(trade_date: str, code: str, ts: str) -> str:
    """构造 open_reason 的兜底匹配键。

    当异步下单拿不到 order_id 时，用 trade_date/code/ts 组成稳定键；
    桥接回报回填时也使用同一键命中。
    """
    return f"{trade_date}:{code}:{ts}"


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _append_line(path: str, payload: dict[str, Any]) -> None:
    with _write_lock:
        _ensure_parent(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _read_all(path: str) -> list[dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    out: list[dict[str, Any]] = []
    with open_shared_read(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _write_lines(path: str, payloads: Iterable[dict[str, Any]]) -> None:
    with _file_write_lock(path):
        _write_lines_unlocked(path, payloads)


@contextmanager
def _file_write_lock(path: str):
    """进程间互斥锁，避免多个盘中/竞价进程并发替换同一个 JSONL。

    锁文件与目标文件同目录，Windows 下用 msvcrt 锁定首字节；非 Windows
    环境退化为无跨进程互斥（进程内仍由 _write_lock 保护写盘）。"""
    lock_path = path + ".lock"
    _ensure_parent(lock_path)
    lock_file = None
    try:
        lock_file = open(lock_path, "a+b")
        if os.fstat(lock_file.fileno()).st_size == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if msvcrt is not None:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        if lock_file is not None:
            try:
                lock_file.seek(0)
                if msvcrt is not None:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                lock_file.close()


def _write_lines_unlocked(path: str, payloads: Iterable[dict[str, Any]]) -> None:
    with _write_lock:
        _ensure_parent(path)
        parent = os.path.dirname(path) or "."
        fd, tmp = tempfile.mkstemp(prefix=".expectation.", suffix=".tmp", dir=parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for payload in payloads:
                    f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        if not replace_file_retry(tmp, path):
            raise PermissionError(f"替换预期文件失败（重试后仍被占用）: {path}")


def append_open_reason(record: OpenReasonRecord | dict[str, Any], path: str | None = None) -> None:
    """落一条开仓理由。"""
    if isinstance(record, OpenReasonRecord):
        payload = record.to_dict()
    else:
        payload = dict(record)
    if not payload.get("ts"):
        payload["ts"] = datetime.now().isoformat(timespec="milliseconds")
    if not payload.get("order_id") and not payload.get("fallback_key"):
        payload["fallback_key"] = build_open_reason_fallback_key(
            str(payload.get("trade_date") or ""),
            str(payload.get("code") or ""),
            str(payload.get("ts") or ""),
        )
    target = path or default_open_reason_path(str(payload.get("trade_date") or ""))
    _append_line(target, payload)


def update_open_reason_status(
    order_id: str,
    status: str,
    filled_volume: int | None = None,
    filled_price: float | None = None,
    path: str | None = None,
    fallback_key: str = "",
) -> bool:
    """按 order_id 或兜底键回填开仓理由状态（filled/cancelled/rejected/partial 等）。

    open_reason 是 append-only JSONL，这里做同文件重写，避免引入第二份状态文件。
    实盘异步下单早期可能只有兜底键，后续桥接回报带有 order_id 时也会回写 order_id。
    找不到记录或没有变化时返回 False。
    """
    order_id = str(order_id or "").strip()
    status = str(status or "").strip()
    fallback_key = str(fallback_key or "").strip()
    if not order_id and not fallback_key:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    target = path or default_open_reason_path(today)
    rows = _read_all(target)
    if not rows:
        return False
    changed = False
    now = datetime.now().isoformat(timespec="milliseconds")
    for row in rows:
        row_order_id = str(row.get("order_id") or "").strip()
        row_fallback_key = str(row.get("fallback_key") or "").strip()
        matched = bool(order_id and row_order_id == order_id)
        if not matched and fallback_key and row_fallback_key == fallback_key:
            matched = True
        if not matched:
            continue
        if order_id and row_order_id != order_id:
            row["order_id"] = order_id
            changed = True
        old_status = str(row.get("status") or "")
        if old_status == status and row.get("filled_volume") == filled_volume and row.get("filled_price") == filled_price:
            continue
        row["status"] = status
        row["status_updated_at"] = now
        if filled_volume is not None:
            row["filled_volume"] = filled_volume
        if filled_price is not None:
            row["filled_price"] = filled_price
        changed = True
    if changed:
        _write_lines(target, rows)
    return changed


def append_expectation_record(record: ExpectationRecord | dict[str, Any], path: str | None = None) -> None:
    """落一条次日预期确认结果。"""
    if isinstance(record, ExpectationRecord):
        payload = record.to_dict()
    else:
        payload = dict(record)
    if not payload.get("updated_at"):
        payload["updated_at"] = datetime.now().isoformat(timespec="milliseconds")
    target = path or default_expectation_path(str(payload.get("trade_date") or ""))
    _append_line(target, payload)


def write_expectation_records(
    trade_date: str,
    records: Iterable[ExpectationRecord | dict[str, Any]],
    path: str | None = None,
) -> None:
    """覆盖写入当日预期确认结果（T+1 盘中确认覆盖用）。"""
    payloads: list[dict[str, Any]] = []
    for r in records:
        if isinstance(r, ExpectationRecord):
            payloads.append(r.to_dict())
        else:
            payloads.append(dict(r))
    now = datetime.now().isoformat(timespec="milliseconds")
    for payload in payloads:
        if not payload.get("updated_at"):
            payload["updated_at"] = now
    target = path or default_expectation_path(trade_date)
    with _file_write_lock(target):
        old_rows = _read_all(target)
        by_code: dict[str, dict[str, Any]] = {}
        for row in old_rows:
            code = str(row.get("code") or "")
            if code:
                by_code[code] = row
        for payload in payloads:
            code = str(payload.get("code") or "")
            if not code:
                continue
            by_code[code] = _merge_expectation_payload(payload, by_code.get(code))
        _write_lines_unlocked(target, list(by_code.values()))


def write_expectation_marker(
    trade_date: str,
    marker: dict[str, Any],
    path: str | None = None,
) -> None:
    """覆盖写入当日预期确认空仓标记（无持仓时的合法终态）。"""
    payload = dict(marker)
    payload.setdefault("trade_date", trade_date)
    payload.setdefault("updated_at", datetime.now().isoformat(timespec="milliseconds"))
    target = path or default_expectation_path(trade_date)
    _write_lines(target, [payload])


def _merge_expectation_payload(
    payload: dict[str, Any],
    old: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并同 code 预期记录，保留旧记录中未失效的竞价字段与 extra。"""
    old = old or {}
    merged = dict(old)
    merged.update(payload)
    preserve_fields = (
        "auction_change_pct",
        "opened_above_yesterday",
        "limit_up_within_1m",
        "is_one_word_t1",
        "below_vwap",
        "two_1m_break_above_open",
    )
    for field in preserve_fields:
        if payload.get(field) is None and old.get(field) is not None:
            merged[field] = old[field]
    old_extra = dict(old.get("extra") or {})
    new_extra = dict(payload.get("extra") or {})
    merged["extra"] = {**old_extra, **new_extra}
    return merged


def write_position_reviews(
    trade_date: str,
    records: Iterable[PositionReviewRecord | dict[str, Any]],
    path: str | None = None,
) -> None:
    """覆盖写入当日复盘观点文件（AGENT 发布用）。"""
    payloads: list[dict[str, Any]] = []
    for r in records:
        if isinstance(r, PositionReviewRecord):
            payloads.append(r.to_dict())
        else:
            payloads.append(dict(r))
    target = path or default_review_path(trade_date)
    _write_lines(target, payloads)


def read_position_reviews(trade_date: str, path: str | None = None) -> list[dict[str, Any]]:
    """读取当日复盘观点。"""
    return _read_all(path or default_review_path(trade_date))


def all_open_reasons(trade_date: str, path: str | None = None) -> list[dict[str, Any]]:
    return _read_all(path or default_open_reason_path(trade_date))


def all_expectations(trade_date: str, path: str | None = None) -> list[dict[str, Any]]:
    return _read_all(path or default_expectation_path(trade_date))


def latest_expectation_status_map(
    trade_date: str,
    path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """读取当日所有预期记录，按 code 保留最后一条。"""
    rows = _read_all(path or default_expectation_path(trade_date))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code:
            continue
        item: dict[str, Any] = {
            "status": str(row.get("status") or ""),
            "auction_status": str(row.get("auction_status") or ""),
            "intraday_status": str(row.get("intraday_status") or ""),
            "role": str(row.get("role") or ""),
            "role_detail": str(row.get("role_detail") or ""),
            "junk_follower": bool(row.get("junk_follower")),
            "sell_policy_hint": str(row.get("sell_policy_hint") or ""),
            "reasons": list(row.get("reasons") or []),
            "updated_at": str(row.get("updated_at") or ""),
        }
        for field, value in (
            ("auction_change_pct", row.get("auction_change_pct")),
            ("opened_above_yesterday", row.get("opened_above_yesterday")),
            ("limit_up_within_1m", row.get("limit_up_within_1m")),
            ("is_one_word_t1", row.get("is_one_word_t1")),
            ("below_vwap", row.get("below_vwap")),
            ("two_1m_break_above_open", row.get("two_1m_break_above_open")),
        ):
            if value is not None:
                item[field] = value
        item["extra"] = dict(row.get("extra") or {})
        out[code] = item
    return out


_expectation_status_cache: dict[str, tuple[float, tuple | None, dict[str, dict[str, Any]]]] = {}
_expectation_status_cache_lock = threading.Lock()


def latest_expectation_status_map_cached(
    trade_date: str,
    ttl_sec: float = 3.0,
    path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """带 TTL 的预期状态读取，供盘中每 tick 调用共用。

    文件 mtime/size 变化时立即失效；缓存只服务 builder 高频路径，
    测试与离线校验仍直接调用 latest_expectation_status_map。
    """
    target = path or default_expectation_path(trade_date)
    try:
        st = os.stat(target)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = None
    now = time.monotonic()
    with _expectation_status_cache_lock:
        hit = _expectation_status_cache.get(target)
        if hit is not None and (now - hit[0]) < ttl_sec and hit[1] == sig:
            return hit[2]
    data = latest_expectation_status_map(trade_date, path=path)
    with _expectation_status_cache_lock:
        _expectation_status_cache[target] = (now, sig, data)
    return data


PTRADE_BRIDGE_DIR = os.environ.get("PTRADE_BRIDGE_OUT_DIR", "").strip() or os.path.join(
    _expectation_data_dir(), "ptrade_bridge"
)


def _bridge_out_path(td: str) -> str:
    return os.path.join(PTRADE_BRIDGE_DIR, f"expectation_{td}.csv")



def _ptrade_code(code: str) -> str:
    """AXquant .SH/.SZ/.BJ -> Ptrade .XSHG/.XSHE（Ptrade 规范见 PT/docs-02）。返回空串表示无法映射。"""
    c = str(code or "").strip()
    if not c:
        return ""
    parts = c.split(".")
    head = parts[0]
    suf = parts[1].upper() if len(parts) > 1 else ""
    if suf in ("SH", "SHANGHAI"):
        return head + ".XSHG"
    if suf in ("SZ", "SHENZHEN"):
        return head + ".XSHE"
    if suf in ("BJ", "BEIJING"):
        return head + ".XBJ"   # 北交所在 Ptrade 的后缀以所在券商为准，待定
    # 无后缀：按首位段推断
    if head[:1] in ("6", "5"):
        return head + ".XSHG"
    if head[:1] in ("0", "1", "2", "3"):
        return head + ".XSHE"
    return ""


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0


def export_expectation_csv(trade_date=None, out_path=None, src_path=None):
    """把 position_expectation JSONL 聚合导出为 Ptrade 消费的 CSV（PT/docs/25 契约）。

    表头: code,side,entry_type,expected_status,yesterday_open_pct,expected_auction_change_pct,
          seal_amount_t0,board_name,reason
    文件为 UTF-8（无 BOM）。side 按 status 端末 miss 推 sell，否则 hold。
    """
    td = trade_date or datetime.now().strftime("%Y-%m-%d")
    src = src_path or default_expectation_path(td)
    if out_path is None:
        out_path = _bridge_out_path(td)
    recs = _read_all(src)
    if not recs:
        return 0
    header = [
        "code", "side", "entry_type", "expected_status", "yesterday_open_pct",
        "expected_auction_change_pct", "seal_amount_t0", "board_name", "reason",
    ]
    rows = []
    for r in recs:
        status = str(r.get("status") or "").strip()
        code = _ptrade_code(str(r.get("code") or ""))
        if not code:
            continue
        side = "sell" if status.lower().endswith("miss") else "hold"
        rows.append([
            code, side,
            str(r.get("entry_type") or "normal"),
            status,
            _num(r.get("yesterday_open_pct")),
            _num(r.get("auction_change_pct")),
            _num(r.get("seal_amount_t0")),
            str(r.get("board_name") or ""),
            str(r.get("limit_up_reason") or r.get("reason") or ""),
        ])
    print("[expectation_csv] ->", out_path)
    tmp = out_path + ".tmp"
    _ensure_parent(out_path)
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    replace_file_retry(tmp, out_path)
    return len(rows)

