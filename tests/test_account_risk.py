"""
v1.3 多账户与风控增强单元测试
"""
import json
import pytest
from datetime import datetime

from app import models, schemas, crud


# ========== 交易账户 CRUD 测试 ==========
class TestTradingAccountCRUD:
    def test_create_account(self, db_session):
        acc = crud.create_trading_account(
            db_session,
            name="主账户",
            market=models.MarketType.A,
            fmz_api_key="test_key",
            fmz_secret_key="test_secret",
        )
        assert acc.id is not None
        assert acc.name == "主账户"
        assert acc.market == models.MarketType.A
        assert acc.status == "active"
        assert acc.is_default is False

    def test_get_accounts(self, db_session):
        crud.create_trading_account(db_session, name="A股账户", market=models.MarketType.A)
        crud.create_trading_account(db_session, name="港股账户", market=models.MarketType.HK)
        crud.create_trading_account(db_session, name="美股账户", market=models.MarketType.US)

        all_acc = crud.get_trading_accounts(db_session)
        assert len(all_acc) == 3

        a_acc = crud.get_trading_accounts(db_session, market=models.MarketType.A)
        assert len(a_acc) == 1
        assert a_acc[0].name == "A股账户"

    def test_update_account(self, db_session):
        acc = crud.create_trading_account(db_session, name="原始", market=models.MarketType.A)
        updated = crud.update_trading_account(db_session, acc.id, name="更新后", status="disabled")
        assert updated.name == "更新后"
        assert updated.status == "disabled"

    def test_delete_account(self, db_session):
        acc = crud.create_trading_account(db_session, name="删除测试", market=models.MarketType.A)
        crud.delete_trading_account(db_session, acc.id)
        found = crud.get_trading_account(db_session, acc.id)
        assert found is None

    def test_set_default_account(self, db_session):
        a1 = crud.create_trading_account(db_session, name="账户1", market=models.MarketType.A)
        a2 = crud.create_trading_account(db_session, name="账户2", market=models.MarketType.HK)

        crud.set_default_account(db_session, a1.id)
        assert crud.get_trading_account(db_session, a1.id).is_default is True
        assert crud.get_trading_account(db_session, a2.id).is_default is False

        # 切换默认
        crud.set_default_account(db_session, a2.id)
        assert crud.get_trading_account(db_session, a1.id).is_default is False
        assert crud.get_trading_account(db_session, a2.id).is_default is True

    def test_account_risk_params(self, db_session):
        params = {"max_single_pct": 5.0, "stop_loss_pct": 3.0}
        acc = crud.create_trading_account(
            db_session, name="自定义风控", market=models.MarketType.A,
            risk_params=json.dumps(params),
        )
        found = crud.get_trading_account(db_session, acc.id)
        assert json.loads(found.risk_params)["max_single_pct"] == 5.0

    def test_get_account_not_found(self, db_session):
        assert crud.get_trading_account(db_session, 99999) is None

    def test_update_account_not_found(self, db_session):
        assert crud.update_trading_account(db_session, 99999, name="x") is None

    def test_delete_account_not_found(self, db_session):
        assert crud.delete_trading_account(db_session, 99999) is None


# ========== 风控规则 CRUD 测试 ==========
class TestRiskRuleCRUD:
    def test_create_rule(self, db_session):
        rule = crud.create_risk_rule(
            db_session,
            name="单票仓位限制",
            rule_type="position_limit",
            market=models.MarketType.A,
            params=json.dumps({"max_single_pct": 10}),
        )
        assert rule.id is not None
        assert rule.is_enabled is True
        assert rule.priority == 0

    def test_get_rules(self, db_session):
        crud.create_risk_rule(db_session, name="A股止损", rule_type="stop_loss", market=models.MarketType.A, params="{}")
        crud.create_risk_rule(db_session, name="美股止损", rule_type="stop_loss", market=models.MarketType.US, params="{}")
        crud.create_risk_rule(db_session, name="全局规则", rule_type="daily_loss", market=models.MarketType.A, params="{}")

        a_rules = crud.get_risk_rules(db_session, market=models.MarketType.A)
        assert len(a_rules) == 2

        all_rules = crud.get_risk_rules(db_session)
        assert len(all_rules) == 3

        enabled = crud.get_risk_rules(db_session, enabled_only=True)
        assert len(enabled) == 3

    def test_create_disabled_rule(self, db_session):
        rule = crud.create_risk_rule(
            db_session, name="禁用规则", rule_type="stop_loss",
            market=models.MarketType.A, params="{}", is_enabled=False
        )
        enabled = crud.get_risk_rules(db_session, enabled_only=True)
        assert len(enabled) == 0

    def test_update_rule(self, db_session):
        rule = crud.create_risk_rule(
            db_session, name="原始", rule_type="stop_loss", market=models.MarketType.A, params="{}"
        )
        updated = crud.update_risk_rule(db_session, rule.id, name="更新后", priority=10)
        assert updated.name == "更新后"
        assert updated.priority == 10

    def test_delete_rule(self, db_session):
        rule = crud.create_risk_rule(
            db_session, name="删除测试", rule_type="stop_loss", market=models.MarketType.A, params="{}"
        )
        crud.delete_risk_rule(db_session, rule.id)
        assert crud.get_risk_rule(db_session, rule.id) is None

    def test_account_specific_rules(self, db_session):
        acc = crud.create_trading_account(db_session, name="测试账户", market=models.MarketType.A)
        crud.create_risk_rule(
            db_session, name="全局规则", rule_type="stop_loss", market=models.MarketType.A, params="{}"
        )
        crud.create_risk_rule(
            db_session, name="账户专属规则", rule_type="position_limit",
            market=models.MarketType.A, account_id=acc.id, params="{}"
        )

        account_rules = crud.get_risk_rules(db_session, account_id=acc.id)
        assert len(account_rules) == 2  # 账户专属 + 全局

    def test_rule_not_found(self, db_session):
        assert crud.get_risk_rule(db_session, 99999) is None
        assert crud.update_risk_rule(db_session, 99999, name="x") is None
        assert crud.delete_risk_rule(db_session, 99999) is None


# ========== 风控事件 CRUD 测试 ==========
class TestRiskEventCRUD:
    def test_create_event(self, db_session):
        event = crud.create_risk_event(
            db_session,
            rule_name="单票超限",
            rule_type="position_limit",
            market=models.MarketType.A,
            severity="warning",
            action="alert",
            message="600519.SH 仓位超过10%",
        )
        assert event.id is not None
        assert event.severity == "warning"

    def test_get_events(self, db_session):
        crud.create_risk_event(db_session, rule_name="事件1", rule_type="stop_loss", market=models.MarketType.A, severity="warning", message="m1")
        crud.create_risk_event(db_session, rule_name="事件2", rule_type="stop_loss", market=models.MarketType.A, severity="critical", message="m2")
        crud.create_risk_event(db_session, rule_name="事件3", rule_type="daily_loss", market=models.MarketType.HK, severity="info", message="m3")

        all_events = crud.get_risk_events(db_session)
        assert len(all_events) == 3

        critical = crud.get_risk_events(db_session, severity="critical")
        assert len(critical) == 1
        assert critical[0].rule_name == "事件2"

        a_events = crud.get_risk_events(db_session, market=models.MarketType.A)
        assert len(a_events) == 2

    def test_count_events(self, db_session):
        crud.create_risk_event(db_session, rule_name="E1", rule_type="x", market=models.MarketType.A, severity="warning", message="m")
        crud.create_risk_event(db_session, rule_name="E2", rule_type="x", market=models.MarketType.A, severity="critical", message="m")
        crud.create_risk_event(db_session, rule_name="E3", rule_type="x", market=models.MarketType.HK, severity="info", message="m")

        assert crud.count_risk_events(db_session) == 3
        assert crud.count_risk_events(db_session, severity="critical") == 1
        assert crud.count_risk_events(db_session, market=models.MarketType.A) == 2

    def test_event_with_detail(self, db_session):
        detail = {"symbol": "600519.SH", "current_pct": 12.5, "limit_pct": 10}
        event = crud.create_risk_event(
            db_session, rule_name="测试", rule_type="position_limit",
            market=models.MarketType.A, severity="warning",
            detail=json.dumps(detail),
        )
        found = crud.get_risk_events(db_session)[0]
        assert json.loads(found.detail)["symbol"] == "600519.SH"

    def test_event_pagination(self, db_session):
        for i in range(10):
            crud.create_risk_event(
                db_session, rule_name=f"事件{i}", rule_type="test",
                market=models.MarketType.A, severity="info", message=f"m{i}"
            )
        page1 = crud.get_risk_events(db_session, skip=0, limit=5)
        page2 = crud.get_risk_events(db_session, skip=5, limit=5)
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].id != page2[0].id
