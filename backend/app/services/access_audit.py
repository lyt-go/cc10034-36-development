"""访问审计领域服务：登记访问时按授权状态放行，结清后的旧授权一律拦截。"""
from __future__ import annotations

from typing import Any

from app.services import settlement
from app.services.base import BaseModuleService
from app.store import store


class AccessAuditService(BaseModuleService):
    MODULE = "access_audit"
    ENTITY = "审计记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["记录编号", "访问主体", "目标资源", "访问操作", "访问时间", "请求IP", "访问结果", "敏感等级", "申请编号", "授权版本", "回执编号"]
    REQUIRED_FIELDS = ["记录编号", "访问主体", "目标资源"]
    STATUS_ORDER = ["已记录", "需复核", "已异常"]
    ACTION_RULES = {"标记复核": "需复核", "标记异常": "已异常"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, missing
        denial = self._grant_denial(values)
        if denial:
            return None, [denial]
        entry, _ = super().create_entry(values)
        assert entry is not None
        entry["登记序号"] = settlement.tick()
        return entry, []

    def _grant_denial(self, values: dict[str, Any]) -> str | None:
        """访问放行校验：关联授权的访问必须持有可用授权版本。

        已结清的授权不再放行新访问；已过期未结清的仍接收迟到回执，
        留待结清时核对；未关联授权的记录按独立审计登记。
        """
        code = str(values.get("申请编号") or "").strip()
        if not code:
            return None
        grant = next(
            (row for row in store.rows("grant_approval")
             if str(row.get("申请编号", "")) == code),
            None,
        )
        if grant is None:
            return f"关联授权 {code} 不存在，访问不得放行"
        version = str(values.get("授权版本") or "").strip()
        if version and version != str(grant.get("授权版本", "")):
            return (
                f"授权版本不一致：访问持 {version}，授权 {code} 当前版本 "
                f"{grant.get('授权版本')}，访问不得放行"
            )
        status = grant.get("status")
        if status == "已结清":
            return f"授权 {code} 已结清，新访问不得借旧授权通过"
        if status == "已拒绝":
            return f"授权 {code} 已拒绝，访问不得放行"
        if status == "待审批":
            return f"授权 {code} 尚未批准，访问不得放行"
        if status == "已批准" and not settlement.in_validity(grant, values.get("访问时间")):
            return f"访问时间超出授权 {code} 有效期，访问不得放行"
        return None
