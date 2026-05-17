"""
Futumock 冒烟测试 — 验证风控 pass / violated 两条路径

路径A：风控 pass → Futu 调用 → signal=EXECUTED + trade_record 创建
路径B：风控 violated → 不调用 Futu → 返回风控拦截（4xx/error）

测试目标：POST /api/v1/futu/execute/{signal_id}?account_id=<id>
认证：current_user（JWT via get_current_user）
信号状态：PENDING → EXECUTED / FAILED
"""

import sys
import os
import uuid
from datetime import datetime, date
from unittest.mock import MagicMock, patch
from typing import Any, Dict

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import crud, models, schemas
from app.api import execute_signal_on_futu


# ===========================================================================
# 辅助 mock 类
# ===========================================================================

class MockExecutionResult:
    """模拟 FutuExecutionProvider.execute_signal 的返回值"""
    def __init__(self, status="success", message="mocked", order_id=None):
        self.status = status
        self.message = message
        self.order_id = order_id or f"mo_{uuid.uuid4().hex[:8]}"
        self.filled_quantity = 100
        self.filled_price = 400.0
        self.positions = None
        self.capital = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": "mock",
            "status": self.status,
            "message": self.message,
            "order_id": self.order_id,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "positions": [],
            "capital": {},
        }


# ===========================================================================
# DB fixtures
# ===========================================================================

TEST_DB_URL = "sqlite:///:memory:"


def _make_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def engine():
    return _make_engine()


@pytest.fixture
def db_session(engine):
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def signal_id(db_session) -> int:
    """在 DB 中创建一个 PENDING 状态的信号，返回其 id"""
    sig = models.TradingSignal(
        signal_id=f"sig_{uuid.uuid4().hex[:12]}",
        symbol="HK.00700",
        market=models.MarketType.HK,
        side="BUY",
        strategy_id="test_strategy",
        strategy_name="TestStrategy",
        signal_type="OPEN",
        confidence=0.85,
        target_price=400.0,
        stop_loss=380.0,
        take_profit=420.0,
        quantity=100.0,
        status="PENDING",
        reason="smoke test",
    )
    db_session.add(sig)
    db_session.commit()
    db_session.refresh(sig)
    return sig.id


@pytest.fixture
def account_id(db_session) -> int:
    """在 DB 中创建一个交易账户，返回其 id"""
    acct = models.TradingAccount(
        name="TestAccount",
        market=models.MarketType.HK,
        trd_env="SIMULATE",
        status="active",
        total_pnl=0.0,
        today_pnl=0.0,
        total_trades=0,
    )
    db_session.add(acct)
    db_session.commit()
    db_session.refresh(acct)
    return acct.id


# ===========================================================================
# 路径A：风控 pass → Futu 调用 → signal=EXECUTED + trade_record 创建
# ===========================================================================

class TestTradingSmokePathA:
    """风控校验通过，信号执行成功"""

    def test_risk_pass_triggers_futu_and_marks_executed(
        self, db_session, signal_id, account_id
    ):
        # ── 1. Mock Futu client ──────────────────────────────────────
        mock_client = MagicMock()
        mock_client.connect.return_value = None
        mock_client.close.return_value = None
        mock_client.execute_signal.return_value = MockExecutionResult(
            status="success", message="订单已发送"
        )

        # ── 2. Mock risk check → 无违规（返回 ok） ────────────────────
        mock_risk_ok = MagicMock()
        mock_risk_ok.status = "ok"      # ← 不是 "violated"
        mock_risk_ok.message = "passed"
        mock_risk_ok.rule_type = "position_limit"

        def fake_get_trading_signal(db, sig_id):
            return db_session.query(models.TradingSignal).filter_by(id=sig_id).first()

        def fake_update_status(db, sig_id, status, executed_at=None):
            sig = db_session.query(models.TradingSignal).filter_by(id=sig_id).first()
            if sig:
                sig.status = status
                sig.executed_at = executed_at or datetime.now()
                db_session.commit()

        def fake_create_trade_record(db, trade_create: schemas.TradeRecordCreate):
            record = models.TradeRecord(
                symbol=trade_create.symbol,
                market=trade_create.market,
                side=trade_create.side,
                quantity=trade_create.quantity,
                price=trade_create.price,
                amount=trade_create.amount,
                strategy_id=trade_create.strategy_id,
                strategy_name=trade_create.strategy_name,
                signal_id=trade_create.signal_id,
                status=trade_create.status or "PENDING",
            )
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return record

        # ── 3. Patch + 调用
        # run_risk_check 在 account_api 模块中定义，直接 patch 该模块路径
        with patch("app.api._build_futu_client", return_value=mock_client), \
             patch("app.api.crud.get_trading_signal", side_effect=fake_get_trading_signal), \
             patch("app.api.crud.update_trading_signal_status", side_effect=fake_update_status), \
             patch("app.api.crud.create_trade_record", side_effect=fake_create_trade_record), \
             patch("app.account_api.run_risk_check", return_value=[mock_risk_ok]):

            resp = execute_signal_on_futu(
                signal_id=signal_id,
                account_id=account_id,
                db=db_session,
                current_user={"id": 1, "username": "test"},
            )

        # ── 4. 断言 ──────────────────────────────────────────────────
        assert resp.success is True, f"Expected success=True, got: {resp.message}"

        # signal.status → EXECUTED
        sig = db_session.query(models.TradingSignal).filter_by(id=signal_id).first()
        assert sig.status == "EXECUTED", f"Expected EXECUTED, got={sig.status}"

        # trade_record 创建
        trades = db_session.query(models.TradeRecord).filter_by(signal_id=signal_id).all()
        assert len(trades) >= 1, f"Expected >=1 trade record, got {len(trades)}"
        assert trades[0].status == "PENDING"

        # Futu execute_signal 被调用（一次）
        assert mock_client.execute_signal.call_count == 1, \
            f"Expected 1 Futu call, got {mock_client.execute_signal.call_count}"


# ===========================================================================
# 路径B：风控 violated → 不调用 Futu → signal.status 保持 PENDING
# ===========================================================================

class TestTradingSmokePathB:
    """风控违规，信号被拦截"""

    def test_risk_violated_returns_error_and_signal_unchanged(
        self, db_session, signal_id, account_id
    ):
        # ── 1. Mock risk check → violated ────────────────────────────
        mock_violation = MagicMock()
        mock_violation.status = "violated"      # ← 触发拦截
        mock_violation.message = "今日亏损超限 (¥-5000 > ¥-3000)"
        mock_violation.rule_type = "daily_loss"

        mock_client = MagicMock()   # 不应被调用

        def fake_get_trading_signal(db, sig_id):
            return db_session.query(models.TradingSignal).filter_by(id=sig_id).first()

        with patch("app.api._build_futu_client", return_value=mock_client), \
             patch("app.api.crud.get_trading_signal", side_effect=fake_get_trading_signal), \
             patch("app.account_api.run_risk_check", return_value=[mock_violation]):

            resp = execute_signal_on_futu(
                signal_id=signal_id,
                account_id=account_id,
                db=db_session,
                current_user={"id": 1, "username": "test"},
            )

        # ── 2. 断言 ──────────────────────────────────────────────────
        assert resp.success is False, f"Expected success=False, got: {resp.success}"
        assert "风控" in resp.message or "violated" in resp.message.lower(), \
            f"Expected risk block message, got: {resp.message}"

        # signal.status 保持 PENDING
        sig = db_session.query(models.TradingSignal).filter_by(id=signal_id).first()
        assert sig.status == "PENDING", f"Expected PENDING, got={sig.status}"

        # Futu 未被调用
        assert mock_client.connect.call_count == 0, \
            "Futu connect should NOT be called when risk violated"
        assert mock_client.execute_signal.call_count == 0, \
            "Futu execute_signal should NOT be called when risk violated"


# ===========================================================================
# 补充：风控 pass 但 Futu 执行失败 → signal=FAILED
# ===========================================================================

class TestTradingSmokeFutuFailure:
    """Futu 执行失败时，signal.status 应收为 FAILED"""

    def test_futu_failure_marks_signal_failed(
        self, db_session, signal_id, account_id
    ):
        # ── 1. Mock risk check → ok ──────────────────────────────────
        mock_risk_ok = MagicMock()
        mock_risk_ok.status = "ok"
        mock_risk_ok.message = "passed"
        mock_risk_ok.rule_type = "position_limit"

        # ── 2. Mock Futu → 返回失败 ─────────────────────────────────
        mock_client = MagicMock()
        mock_client.connect.return_value = None
        mock_client.close.return_value = None
        mock_client.execute_signal.return_value = MockExecutionResult(
            status="failed", message="资金不足"
        )

        def fake_get_trading_signal(db, sig_id):
            return db_session.query(models.TradingSignal).filter_by(id=sig_id).first()

        def fake_update_status(db, sig_id, status, executed_at=None):
            sig = db_session.query(models.TradingSignal).filter_by(id=sig_id).first()
            if sig:
                sig.status = status
                sig.executed_at = executed_at or datetime.now()
                db_session.commit()

        with patch("app.api._build_futu_client", return_value=mock_client), \
             patch("app.api.crud.get_trading_signal", side_effect=fake_get_trading_signal), \
             patch("app.api.crud.update_trading_signal_status", side_effect=fake_update_status), \
             patch("app.account_api.run_risk_check", return_value=[mock_risk_ok]):

            resp = execute_signal_on_futu(
                signal_id=signal_id,
                account_id=account_id,
                db=db_session,
                current_user={"id": 1, "username": "test"},
            )

        assert resp.success is False, f"Expected success=False, got: {resp.success}"
        sig = db_session.query(models.TradingSignal).filter_by(id=signal_id).first()
        assert sig.status == "FAILED", f"Expected FAILED, got={sig.status}"