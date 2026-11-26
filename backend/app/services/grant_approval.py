"""授权审批领域服务：审批流转之外，支持过期授权的结清核对与回执生成。"""
from __future__ import annotations

from typing import Any

from app.services import settlement
from app.services.base import BaseModuleService
from app.store import store


class GrantApprovalService(BaseModuleService):
    MODULE = "grant_approval"
    ENTITY = "授权申请"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["申请编号", "申请人", "目标数据", "使用目的", "有效期起", "有效期止", "访问级别", "审批状态", "授权版本"]
    REQUIRED_FIELDS = ["申请编号", "申请人", "目标数据"]
    STATUS_ORDER = ["待审批", "已批准", "已拒绝", "已过期", "已结清"]
    ACTION_RULES = {"批准申请": "已批准", "拒绝申请": "已拒绝", "标记过期": "已过期", "结清授权": "已结清"}
    NEGATIVE_ACTIONS = ["拒绝申请"]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        values = dict(values)
        if not str(values.get("授权版本") or "").strip():
            values["授权版本"] = "v1"
        return super().create_entry(values)

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        if entry.get("status") == "已结清" and action != "结清授权":
            return None, f"{self.ENTITY}已结清，不允许再执行「{action}」"
        if action == "结清授权":
            return self._settle(entry)
        if action == "标记过期":
            entry, message = super().run_action(entry_id, action)
            if entry is not None and not entry.get("过期序号"):
                entry["过期序号"] = settlement.tick()
            return entry, message
        return super().run_action(entry_id, action)

    def _settle(self, entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """结清授权：核对访问审计后生成回执；重复结清幂等沿用原回执。"""
        existing = entry.get("结清回执")
        if entry.get("status") == "已结清" and existing:
            return entry, f"{self.ENTITY}已结清，沿用回执 {existing['回执编号']}"
        if entry.get("status") != "已过期":
            return None, f"仅已过期的{self.ENTITY}可结清，当前状态：{entry.get('status')}"
        receipt, _ = settlement.execute_settlement(entry)
        entry["status"] = "已结清"
        entry["pending"] = False
        entry["abnormal"] = False
        return entry, (
            f"{self.ENTITY}已结清，回执 {receipt['回执编号']}："
            f"计入 {receipt['计入数量']} 笔，未决 {receipt['未决数量']} 笔，"
            f"重复回执 {receipt['重复回执数']} 笔"
        )

    def settlement_panel(self, entry_id: int) -> dict[str, Any] | None:
        """结清面板：核对本授权版本下的已确认/未决访问，或查看已生成的回执。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None
        return settlement.build_panel(entry)
