"""授权结清：按授权版本核对访问审计记录，生成授权结清回执。

结清规则：
- 只核对「申请编号 + 授权版本」与授权单一致的审计记录，别的授权的访问不计入本单；
- 同一回执编号只计一次，重复报告列入「重复回执」不多计；
- 访问时间落在有效期内的计入结清；有效期外或缺访问时间的仍需复核；
- 授权标记过期后才登记（回执迟到）但访问时间在有效期内的，仍计入本次结清并标记迟到；
- 结清幂等：已结清的授权沿用原回执，不会重复计数。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

# 单调序号：给「标记过期」和「审计登记」排先后，识别回执迟到，
# 不依赖墙钟，避免同一秒内时间戳相等导致误判。
_seq = 0


def tick() -> int:
    """返回全局单调递增序号。"""
    global _seq
    _seq += 1
    return _seq


def _date_part(value: Any) -> str:
    return str(value or "").strip()[:10]


def in_validity(grant: dict[str, Any], visit_time: Any) -> bool:
    """访问时间（按日期部分比较）是否落在授权有效期内。"""
    day = _date_part(visit_time)
    if not day:
        return False
    start = _date_part(grant.get("有效期起"))
    end = _date_part(grant.get("有效期止"))
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def linked_records(grant: dict[str, Any]) -> list[dict[str, Any]]:
    """按申请编号 + 授权版本核对访问审计记录，别的授权一律排除。"""
    code = str(grant.get("申请编号", ""))
    version = str(grant.get("授权版本", ""))
    rows = [
        row for row in store.rows("access_audit")
        if str(row.get("申请编号", "")) == code
        and str(row.get("授权版本", "")) == version
    ]
    return sorted(rows, key=lambda row: int(row.get("id", 0)))


def _is_late(grant: dict[str, Any], row: dict[str, Any]) -> bool:
    """回执是否迟到：授权标记过期之后才登记进审计。"""
    expire_seq = int(grant.get("过期序号") or 0)
    register_seq = int(row.get("登记序号") or 0)
    return bool(expire_seq and register_seq and register_seq > expire_seq)


def classify_records(
    grant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """把关联审计记录分成（计入结清、仍需复核、重复回执）三组。"""
    confirmed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in linked_records(grant):
        receipt = str(row.get("回执编号") or "").strip()
        key = receipt or f"id:{row.get('id')}"
        if key in seen:
            duplicates.append(row)
            continue
        seen.add(key)
        item = {"row": row, "迟到": _is_late(grant, row)}
        if in_validity(grant, row.get("访问时间")):
            confirmed.append(item)
        else:
            pending.append(item)
    return confirmed, pending, duplicates


def _line(row: dict[str, Any], *, late: bool, disposition: str) -> dict[str, Any]:
    return {
        "记录编号": row.get("记录编号"),
        "访问主体": row.get("访问主体"),
        "访问时间": row.get("访问时间"),
        "回执编号": row.get("回执编号"),
        "迟到": late,
        "处理": disposition,
    }


def build_panel(grant: dict[str, Any]) -> dict[str, Any]:
    """结清面板数据：未结清时给出核对预览，已结清时返回回执与明细。"""
    confirmed, pending, duplicates = classify_records(grant)
    return {
        "申请编号": grant.get("申请编号"),
        "授权版本": grant.get("授权版本"),
        "状态": grant.get("status"),
        "有效期起": grant.get("有效期起"),
        "有效期止": grant.get("有效期止"),
        "可结清": grant.get("status") == "已过期",
        "已确认": [
            _line(item["row"], late=item["迟到"], disposition="计入本次结清")
            for item in confirmed
        ],
        "未决": [
            _line(item["row"], late=item["迟到"], disposition="仍需复核")
            for item in pending
        ],
        "重复回执": [
            _line(row, late=_is_late(grant, row), disposition="重复回执-不计入")
            for row in duplicates
        ],
        "结清回执": grant.get("结清回执"),
    }


def execute_settlement(grant: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """执行结清：生成回执、回写审计记录处理结果。已结清则幂等返回原回执。"""
    existing = grant.get("结清回执")
    if existing:
        return existing, False

    confirmed, pending, duplicates = classify_records(grant)
    settled_count = sum(
        1 for row in store.rows("grant_approval") if row.get("结清回执")
    )
    receipt_no = f"SETL-{grant.get('申请编号')}-{settled_count + 1:04d}"
    details = [
        _line(item["row"], late=item["迟到"], disposition="计入本次结清")
        for item in confirmed
    ]
    details += [
        _line(item["row"], late=item["迟到"], disposition="仍需复核")
        for item in pending
    ]
    details += [
        _line(row, late=_is_late(grant, row), disposition="重复回执-不计入")
        for row in duplicates
    ]
    receipt = {
        "回执编号": receipt_no,
        "申请编号": grant.get("申请编号"),
        "授权版本": grant.get("授权版本"),
        "结清时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "计入数量": len(confirmed),
        "未决数量": len(pending),
        "重复回执数": len(duplicates),
        "明细": details,
    }

    for item in confirmed:
        item["row"]["结清处理"] = "计入结清"
        item["row"]["结清回执编号"] = receipt_no
    for item in pending:
        item["row"]["结清处理"] = "仍需复核"
        item["row"]["结清回执编号"] = receipt_no
        item["row"]["status"] = "需复核"
        item["row"]["pending"] = True
    for row in duplicates:
        row["结清处理"] = "重复回执-不计入"
        row["结清回执编号"] = receipt_no

    grant["结清回执"] = receipt
    return receipt, True
