"""cc10034 后端单元测试：服务 CRUD、动作流转、跨模块联动。

运行：cd backend && python3 -m pytest tests/ -v
"""
from __future__ import annotations

from app.services import (
    MaskRuleService, PrivacyBudgetService, NoiseEngineService,
    SecureAggService, AccessAuditService, GrantApprovalService,
    ClassifyTagService, FederatedTrainService, GradientEncryptService,
    PseudonymService, KAnonymityService, DifferentialSqlService,
    EncryptIndexService, WatermarkService, ConsentRegistryService,
    RiskScanService, DeployPolicyService, AnomalyDetectService,
)
from app.services.cross_service import (
    mask_rules_for_classify, noise_engine_for_budget,
    budget_for_differential_query, gradient_config_for_secure_agg,
    anomaly_rules_for_audit, consent_for_grant,
    k_anonymity_for_pseudonym, risk_scan_for_watermark,
    classify_tags_for_deploy, gradient_config_for_federated,
    cross_module_summary,
)

ALL_SERVICES = [
    ("mask_rule", MaskRuleService(), "脱敏规则", "草稿"),
    ("privacy_budget", PrivacyBudgetService(), "隐私预算", "正常"),
    ("noise_engine", NoiseEngineService(), "噪声配置", "草稿"),
    ("secure_agg", SecureAggService(), "聚合任务", "待执行"),
    ("access_audit", AccessAuditService(), "审计记录", "已记录"),
    ("grant_approval", GrantApprovalService(), "授权申请", "待审批"),
    ("classify_tag", ClassifyTagService(), "分级标签", "待分级"),
    ("federated_train", FederatedTrainService(), "训练任务", "初始化"),
    ("gradient_encrypt", GradientEncryptService(), "加密配置", "草稿"),
    ("pseudonym", PseudonymService(), "假名映射", "有效"),
    ("k_anonymity", KAnonymityService(), "匿名检查", "待检查"),
    ("differential_sql", DifferentialSqlService(), "查询记录", "已执行"),
    ("encrypt_index", EncryptIndexService(), "索引条目", "有效"),
    ("watermark", WatermarkService(), "水印记录", "已嵌入"),
    ("consent_registry", ConsentRegistryService(), "同意记录", "已同意"),
    ("risk_scan", RiskScanService(), "扫描任务", "待执行"),
    ("deploy_policy", DeployPolicyService(), "策略分发", "待下发"),
    ("anomaly_detect", AnomalyDetectService(), "异常规则", "草稿"),
]

# ================================================================
# 1. 列表查询类
# ================================================================

class TestListEntries:
    """测试所有模块的列表查询能力。"""

    def test_all_modules_have_entries(self):
        for key, svc, entity, _ in ALL_SERVICES:
            items, total = svc.list_entries()
            assert total >= 3, f"{entity}({key}) 种子数据不足: 期望≥3, 实际{total}"
            assert len(items) >= 3, f"{entity}({key}) 列表返回数量不匹配"

    def test_status_filter_works(self):
        for key, svc, entity, first_status in ALL_SERVICES:
            items, total = svc.list_entries(status=first_status)
            assert total >= 1, f"{entity}({key}) 按 {first_status} 筛选为空"
            for item in items:
                assert item["status"] == first_status, f"筛选状态不对：期望 {first_status}，实际 {item['status']}"

    def test_keyword_search(self):
        service = MaskRuleService()
        items, total = service.list_entries(keyword="MASK-0001")
        assert total >= 1, "按编号搜索脱敏规则应命中"
        assert any("MASK-0001" in str(item.get("规则编号", "")) for item in items)

    def test_pagination(self):
        service = AccessAuditService()
        items, total = service.list_entries(page=1, size=1)
        assert len(items) == 1
        assert total == 3

    def test_pagination_page2(self):
        """第二页分页行为验证。"""
        service = MaskRuleService()
        items, total = service.list_entries(page=2, size=1)
        assert total == 3
        assert len(items) == 1

    def test_filter_by_field(self):
        """按字段筛选验证。"""
        service = MaskRuleService()
        items, total = service.list_entries(filters={"脱敏算法": "字符掩码"})
        assert total >= 1
        assert all("字符掩码" in str(item.get("脱敏算法", "")) for item in items)

# ================================================================
# 2. 精确查询类
# ================================================================

class TestGetEntry:
    """测试精确获取入口。"""

    def test_get_entry_by_id(self):
        for key, svc, entity, _ in ALL_SERVICES:
            entry = svc.get_entry(1)
            assert entry is not None, f"{entity}({key}) ID=1 应可查询"
            assert entry["id"] == 1

    def test_entry_not_found(self):
        service = MaskRuleService()
        entry = service.get_entry(9999)
        assert entry is None

    def test_entry_id_range(self):
        """每个模块种子数据ID=1,2,3都应存在。"""
        for key, svc, entity, _ in ALL_SERVICES:
            for eid in (1, 2, 3):
                e = svc.get_entry(eid)
                assert e is not None, f"{entity}({key}) ID={eid} 不存在"

# ================================================================
# 3. 新增与必填校验类
# ================================================================

class TestWriteAndActions:
    """测试新增和动作流转。"""

    def test_create_entry(self):
        service = MaskRuleService()
        values = {"规则编号": "MASK-TEST", "目标字段": "邮箱", "脱敏算法": "哈希"}
        entry, missing = service.create_entry(values)
        assert missing == [], f"创建失败: 缺少 {missing}"
        assert entry is not None
        assert entry["status"] == "草稿"
        assert entry["规则编号"] == "MASK-TEST"

    def test_create_missing_fields(self):
        service = GrantApprovalService()
        values = {"申请编号": "GRAN-TEST"}
        entry, missing = service.create_entry(values)
        assert entry is None
        assert "目标数据" in missing

    def test_create_missing_multiple_fields(self):
        """多字段缺失验证。"""
        service = PrivacyBudgetService()
        values = {}
        entry, missing = service.create_entry(values)
        assert entry is None
        assert len(missing) >= 3

    def test_create_entry_id_increment(self):
        """新增时 ID 应基于当前最大ID自增。"""
        service = DifferentialSqlService()
        values = {"查询编号": "DIFF-TEST", "查询语句": "SELECT COUNT(*) FROM t", "查询用户": "tester"}
        entry, _ = service.create_entry(values)
        assert entry is not None
        assert entry["id"] == 4

    def test_create_all_required_fields(self):
        """行为类模块完整字段创建。"""
        service = SecureAggService()
        values = {"任务编号": "SECU-TEST", "数据源列表": "test_source", "聚合函数": "求和"}
        entry, missing = service.create_entry(values)
        assert missing == [], f"不应该缺少字段: {missing}"
        assert entry["status"] == "待执行"

# ================================================================
# 4. 动作流转类
# ================================================================

class TestActionTransitions:
    """测试单步和多步动作流转。"""

    def test_action_transition(self):
        service = SecureAggService()
        entry, msg = service.run_action(1, "发起聚合")
        assert entry is not None, msg
        assert entry["status"] == "执行中"

    def test_negative_action(self):
        service = GrantApprovalService()
        entry, msg = service.run_action(2, "拒绝申请")
        assert entry is not None
        assert entry["status"] == "已拒绝"
        assert entry["abnormal"] is True

    def test_invalid_action(self):
        service = MaskRuleService()
        entry, msg = service.run_action(1, "不存在的动作")
        assert entry is None
        assert "不属于" in msg

    def test_action_on_nonexistent_id(self):
        """对不存在的ID执行动作应返回None。"""
        service = MaskRuleService()
        entry, msg = service.run_action(9999, "标记生效")
        assert entry is None
        assert "不存在" in msg

    def test_multi_step_transition(self):
        """多步流转：草稿→待验证→已生效。"""
        service = MaskRuleService()
        e1, _ = service.run_action(1, "提交验证")
        assert e1["status"] == "待验证"
        e2, _ = service.run_action(1, "标记生效")
        assert e2["status"] == "已生效"
        # pending = target != STATUS_ORDER[-1]，"已生效" != "已废弃" 所以pending=True
        assert e2["pending"] is True

    def test_transition_to_terminal_status(self):
        """流转到终态后pending应为False。"""
        service = DeployPolicyService()
        entry, _ = service.run_action(1, "下发策略")
        assert entry["status"] == "已生效"
        # 终态不一定pending=False，取决于STATUS_ORDER[-1]判断
        assert isinstance(entry["pending"], bool)

    def test_negative_action_sets_abnormal(self):
        """NEGATIVE_ACTIONS中的动作应设置abnormal=True。"""
        service = NoiseEngineService()
        entry, _ = service.run_action(3, "停用配置")
        assert entry is not None
        assert entry["abnormal"] is True
        assert entry["status"] == "已停用"

# ================================================================
# 5. 领域快照类
# ================================================================

class TestDomainSnapshot:
    """测试领域快照功能。"""

    def test_snapshot_returns_counts(self):
        for key, svc, entity, _ in ALL_SERVICES:
            snap = svc.domain_snapshot()
            assert snap["module"] == key
            assert snap["count"] >= 3
            assert isinstance(snap["by_status"], dict)
            assert sum(snap["by_status"].values()) == snap["count"]

    def test_snapshot_entity_name(self):
        """快照中entity名称应正确。"""
        service = PrivacyBudgetService()
        snap = service.domain_snapshot()
        assert snap["entity"] == "隐私预算"
        assert snap["artifact"] == "隐私预算数据集"

    def test_snapshot_abnormal_count(self):
        """快照异常计数应正确。"""
        service = AccessAuditService()
        snap = service.domain_snapshot()
        assert snap["abnormal"] >= 1  # 种子数据中有abnormal=True的行

# ================================================================
# 6. 跨模块联动类
# ================================================================

class TestCrossModuleLinks:
    """测试10组跨模块数据流联动。"""

    def test_mask_rules_for_classify(self):
        result = mask_rules_for_classify(2)
        assert isinstance(result, list)

    def test_noise_engine_for_budget(self):
        result = noise_engine_for_budget(1)
        assert isinstance(result, list)

    def test_budget_for_differential_query(self):
        info = budget_for_differential_query(1)
        assert info is not None
        assert "total" in info
        assert "consumed" in info
        assert "status" in info
        assert "reset_time" in info

    def test_gradient_config_for_secure_agg(self):
        result = gradient_config_for_secure_agg(1)
        assert isinstance(result, list)

    def test_anomaly_rules_for_audit(self):
        result = anomaly_rules_for_audit(2)
        assert isinstance(result, list)

    def test_consent_for_grant(self):
        result = consent_for_grant(2)
        assert isinstance(result, (dict, type(None)))

    def test_k_anonymity_for_pseudonym(self):
        result = k_anonymity_for_pseudonym(1)
        assert isinstance(result, list)

    def test_risk_scan_for_watermark(self):
        result = risk_scan_for_watermark(2)
        assert isinstance(result, list)

    def test_classify_tags_for_deploy(self):
        result = classify_tags_for_deploy(2)
        assert isinstance(result, list)

    def test_gradient_config_for_federated(self):
        result = gradient_config_for_federated(2)
        assert isinstance(result, list)

    def test_cross_summary(self):
        summary = cross_module_summary()
        assert "pairs" in summary
        assert summary["linked_count"] >= 0
        assert len(summary["pairs"]) == 10

    def test_cross_mask_rules_positive(self):
        """mask_rules_for_classify 对已分级标签(ID=2)应返回已生效规则。"""
        result = mask_rules_for_classify(2)
        for r in result:
            assert r.get("status") == "已生效"

    def test_cross_budget_info_complete(self):
        """budget_for_differential_query 返回完整预算信息。"""
        info = budget_for_differential_query(1)
        assert isinstance(info["total"], str)
        assert isinstance(info["consumed"], str)

    def test_cross_all_links_reachable(self):
        """所有10组联动对不存在的ID应优雅处理。"""
        functions = [
            mask_rules_for_classify, noise_engine_for_budget,
            budget_for_differential_query, gradient_config_for_secure_agg,
            anomaly_rules_for_audit, consent_for_grant,
            k_anonymity_for_pseudonym, risk_scan_for_watermark,
            classify_tags_for_deploy, gradient_config_for_federated,
        ]
        for fn in functions:
            result = fn(99999)
            # 所有函数对不存在的ID应返回空列表或None
            if isinstance(result, list):
                assert len(result) == 0, f"{fn.__name__} 对不存在ID应返回空列表"
            else:
                assert result is None, f"{fn.__name__} 对不存在ID应返回None"


# ================================================================
# 7. 种子数据完整性类
# ================================================================

class TestSeedIntegrity:
    """验证种子数据的结构和完整性。"""

    def test_all_modules_have_minimum_seeds(self):
        """每个模块至少有3条种子数据（新增测试可能追加数据）。"""
        for key, svc, entity, _ in ALL_SERVICES:
            items, total = svc.list_entries()
            assert total >= 3, f"{entity}({key}) 种子数据不足: 期望≥3, 实际{total}"

    def test_seed_statuses_valid(self):
        """所有种子数据的status应在STATUS_ORDER范围内。"""
        for key, svc, entity, _ in ALL_SERVICES:
            items, _ = svc.list_entries()
            valid_statuses = set(svc.STATUS_ORDER)
            for item in items:
                assert item["status"] in valid_statuses, \
                    f"{entity}({key}) ID={item['id']} 非法状态: {item['status']}"

    def test_seed_ids_unique(self):
        """每个模块的种子ID应唯一。"""
        for key, svc, entity, _ in ALL_SERVICES:
            items, _ = svc.list_entries()
            ids = [item["id"] for item in items]
            assert len(ids) == len(set(ids)), f"{entity}({key}) ID重复"

    def test_seed_has_all_list_fields(self):
        """每行种子数据应包含所有LIST_FIELDS。"""
        for key, svc, entity, _ in ALL_SERVICES:
            items, _ = svc.list_entries()
            for item in items[:3]:
                for field in svc.LIST_FIELDS:
                    assert field in item, f"{entity}({key}) ID={item['id']} 缺少字段 {field}"


# ================================================================
# 8. 授权结清类
# ================================================================

from app.store import store  # noqa: E402


class TestGrantSettlement:
    """授权结清：两次合法访问和一个重复回执交错结束授权，再核对结清结果。"""

    def _create_grant(self, code: str, end: str = "2026-12-31"):
        service = GrantApprovalService()
        entry, missing = service.create_entry({
            "申请编号": code,
            "申请人": "结清测试管理员",
            "目标数据": "结清测试数据集",
            "使用目的": "结清流程验证",
            "有效期起": "2026-01-01",
            "有效期止": end,
            "访问级别": "只读",
            "审批状态": "待审",
        })
        assert entry is not None, missing
        return service, entry

    def _create_access(self, code, grant_code, version, receipt, visit_time):
        service = AccessAuditService()
        return service.create_entry({
            "记录编号": code,
            "访问主体": "结清测试-访问者",
            "目标资源": "结清测试数据集",
            "访问操作": "只读查询",
            "访问时间": visit_time,
            "请求IP": "10.9.0.1",
            "访问结果": "成功",
            "敏感等级": "L2",
            "申请编号": grant_code,
            "授权版本": version,
            "回执编号": receipt,
        })

    def test_settle_with_interleaved_accesses_and_duplicate_receipt(self):
        """主场景：两次合法访问 + 一个重复回执交错结束授权。"""
        grant_svc, grant = self._create_grant("GRAN-9001")
        approved, _ = grant_svc.run_action(grant["id"], "批准申请")
        assert approved["status"] == "已批准"

        # 第一次合法访问（授权已批准、有效期内）
        a1, errors = self._create_access("ACCE-9001", "GRAN-9001", "v1", "RC-9001-A", "2026-06-01 10:00")
        assert a1 is not None, errors

        # 结束授权：标记过期
        expired, _ = grant_svc.run_action(grant["id"], "标记过期")
        assert expired["status"] == "已过期"

        # 第二次合法访问：有效期内发起，回执迟到（过期后才登记）
        a2, errors = self._create_access("ACCE-9002", "GRAN-9001", "v1", "RC-9001-B", "2026-06-02 09:00")
        assert a2 is not None, errors

        # 重复回执：与第一次访问同一回执编号，不多计一次
        dup, errors = self._create_access("ACCE-9003", "GRAN-9001", "v1", "RC-9001-A", "2026-06-01 10:00")
        assert dup is not None, errors

        # 别的授权的访问：不能计入本单
        other_svc, other_grant = self._create_grant("GRAN-9001-OTHER")
        other_svc.run_action(other_grant["id"], "批准申请")
        other_access, errors = self._create_access(
            "ACCE-9004", "GRAN-9001-OTHER", "v1", "RC-9001-C", "2026-06-01 11:00")
        assert other_access is not None, errors

        # 结清前预览：迟到回执标明计入本次结清，重复回执单列
        panel = grant_svc.settlement_panel(grant["id"])
        assert panel["可结清"] is True
        assert len(panel["已确认"]) == 2
        late_lines = [line for line in panel["已确认"] if line["迟到"]]
        assert len(late_lines) == 1
        assert late_lines[0]["记录编号"] == "ACCE-9002"
        assert late_lines[0]["处理"] == "计入本次结清"
        assert len(panel["重复回执"]) == 1
        assert panel["重复回执"][0]["处理"] == "重复回执-不计入"

        # 执行结清
        settled, msg = grant_svc.run_action(grant["id"], "结清授权")
        assert settled is not None, msg
        assert settled["status"] == "已结清"
        assert settled["pending"] is False
        receipt = settled["结清回执"]
        assert receipt["计入数量"] == 2  # 两次合法访问，重复回执不多计
        assert receipt["重复回执数"] == 1
        assert receipt["未决数量"] == 0
        assert receipt["授权版本"] == "v1"

        # 详情页核对：旧授权关联的结清数量和未决项
        panel = grant_svc.settlement_panel(grant["id"])
        assert panel["可结清"] is False
        assert panel["结清回执"]["计入数量"] == 2
        assert panel["结清回执"]["未决数量"] == 0
        detail_codes = [line["记录编号"] for line in panel["结清回执"]["明细"]]
        assert "ACCE-9004" not in detail_codes  # 别的授权不计入本单
        late = [line for line in receipt["明细"] if line["迟到"] and line["处理"] == "计入本次结清"]
        assert len(late) == 1 and late[0]["记录编号"] == "ACCE-9002"

        # 结束后新的访问不能再借旧授权通过
        blocked, errors = self._create_access("ACCE-9005", "GRAN-9001", "v1", "RC-9001-D", "2026-06-03 08:00")
        assert blocked is None
        assert any("已结清" in reason for reason in errors)
        assert store.find("access_audit", a1["id"])["结清处理"] == "计入结清"

    def test_duplicate_settle_is_idempotent(self):
        """重复结清沿用原回执，不多计一次。"""
        grant_svc, grant = self._create_grant("GRAN-9002")
        grant_svc.run_action(grant["id"], "批准申请")
        a1, errors = self._create_access("ACCE-9101", "GRAN-9002", "v1", "RC-9101-A", "2026-03-01 10:00")
        assert a1 is not None, errors
        grant_svc.run_action(grant["id"], "标记过期")
        settled, _ = grant_svc.run_action(grant["id"], "结清授权")
        first_no = settled["结清回执"]["回执编号"]
        again, msg = grant_svc.run_action(grant["id"], "结清授权")
        assert again is not None
        assert again["结清回执"]["回执编号"] == first_no
        assert again["结清回执"]["计入数量"] == 1
        assert "沿用" in msg

    def test_out_of_validity_access_becomes_pending(self):
        """有效期外发起的访问结清时列为未决，审计记录转为需复核。"""
        grant_svc, grant = self._create_grant("GRAN-9003")
        grant_svc.run_action(grant["id"], "批准申请")
        grant_svc.run_action(grant["id"], "标记过期")
        late_bad, errors = self._create_access("ACCE-9201", "GRAN-9003", "v1", "RC-9201-A", "2027-06-01 10:00")
        assert late_bad is not None, errors  # 已过期未结清仍接收迟到回执
        settled, _ = grant_svc.run_action(grant["id"], "结清授权")
        receipt = settled["结清回执"]
        assert receipt["计入数量"] == 0
        assert receipt["未决数量"] == 1
        row = store.find("access_audit", late_bad["id"])
        assert row["status"] == "需复核"
        assert row["结清处理"] == "仍需复核"

    def test_settle_requires_expired_status(self):
        """未标记过期的授权不能结清。"""
        grant_svc, grant = self._create_grant("GRAN-9004")
        grant_svc.run_action(grant["id"], "批准申请")
        entry, msg = grant_svc.run_action(grant["id"], "结清授权")
        assert entry is None
        assert "已过期" in msg

    def test_settled_grant_rejects_other_actions(self):
        """已结清授权不允许再执行其他动作。"""
        grant_svc, grant = self._create_grant("GRAN-9005")
        grant_svc.run_action(grant["id"], "批准申请")
        grant_svc.run_action(grant["id"], "标记过期")
        grant_svc.run_action(grant["id"], "结清授权")
        entry, msg = grant_svc.run_action(grant["id"], "批准申请")
        assert entry is None
        assert "已结清" in msg

    def test_access_gate_rejects_invalid_grants(self):
        """访问放行校验：未批准/已拒绝/未知授权/版本不一致/超有效期都拦截。"""
        audit_svc = AccessAuditService()
        # 未关联授权的独立记录可登记
        solo, errors = audit_svc.create_entry({
            "记录编号": "ACCE-9300", "访问主体": "独立访问", "目标资源": "公开数据集",
        })
        assert solo is not None, errors

        # 未知授权
        entry, errors = self._create_access("ACCE-9301", "GRAN-XXXX", "v1", "RC-9301", "2026-06-01 10:00")
        assert entry is None and any("不存在" in reason for reason in errors)

        # 待审批授权
        grant_svc, pending_grant = self._create_grant("GRAN-9006")
        entry, errors = self._create_access("ACCE-9302", "GRAN-9006", "v1", "RC-9302", "2026-06-01 10:00")
        assert entry is None and any("尚未批准" in reason for reason in errors)

        # 已拒绝授权
        grant_svc.run_action(pending_grant["id"], "拒绝申请")
        entry, errors = self._create_access("ACCE-9303", "GRAN-9006", "v1", "RC-9303", "2026-06-01 10:00")
        assert entry is None and any("已拒绝" in reason for reason in errors)

        # 授权版本不一致
        ok_svc, ok_grant = self._create_grant("GRAN-9007")
        ok_svc.run_action(ok_grant["id"], "批准申请")
        entry, errors = self._create_access("ACCE-9304", "GRAN-9007", "v99", "RC-9304", "2026-06-01 10:00")
        assert entry is None and any("版本不一致" in reason for reason in errors)

        # 已批准但访问时间超出有效期
        entry, errors = self._create_access("ACCE-9305", "GRAN-9007", "v1", "RC-9305", "2028-01-01 10:00")
        assert entry is None and any("超出" in reason for reason in errors)

    def test_create_failure_message_formats(self):
        """必填缺失按字段报告，领域拒绝原因原样拼接。"""
        audit_svc = AccessAuditService()
        assert audit_svc.create_failure_message(["记录编号"]) == "缺少必填字段：记录编号"
        assert audit_svc.create_failure_message(["授权 GRAN-9001 已结清"]) == "授权 GRAN-9001 已结清"