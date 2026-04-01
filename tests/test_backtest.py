"""
v0.9 回测模块单元测试
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app import models, schemas
from app.backtest_service import (
    _generate_mock_daily_values,
    _generate_mock_trades,
    _generate_mock_feature_importance,
    run_backtest,
)


# ========== 回测 Schema 测试 ==========
class TestBacktestSchemas:
    def test_backtest_config_defaults(self):
        config = schemas.BacktestConfig(name="测试回测")
        assert config.name == "测试回测"
        assert config.strategy_type == "ml_stock_picker"
        assert config.market == schemas.MarketType.A
        assert config.initial_capital == 1_000_000
        assert config.commission == 0.0003
        assert config.top_n == 3
        assert config.model_type == "gbm"

    def test_backtest_config_custom(self):
        config = schemas.BacktestConfig(
            name="自定义回测",
            market=schemas.MarketType.HK,
            initial_capital=500_000,
            commission=0.0005,
            top_n=5,
            model_type="rf",
            n_trials=50,
        )
        assert config.market == schemas.MarketType.HK
        assert config.initial_capital == 500_000
        assert config.model_type == "rf"
        assert config.n_trials == 50

    def test_backtest_config_validation(self):
        # 名称不能为空
        with pytest.raises(Exception):
            schemas.BacktestConfig(name="")
        # 初始资金最低 10000
        with pytest.raises(Exception):
            schemas.BacktestConfig(name="x", initial_capital=1000)

    def test_backtest_trade_response(self):
        trade = schemas.BacktestTradeResponse(
            id=1, date="2024-01-15", action="buy",
            code="600519.SH", price=1800.0, shares=100,
            cost=180030.0, commission=54.0
        )
        assert trade.action == "buy"
        assert trade.shares == 100

    def test_backtest_result_response(self):
        result = schemas.BacktestResultResponse(
            id=1, name="测试", strategy_type="ml_stock_picker",
            market="A", status="completed",
            initial_capital=1_000_000, commission=0.0003,
            stamp_tax=0.001, slippage=0.001,
            final_value=1_150_000, total_return=0.15,
            annual_return=0.18, max_drawdown=-0.08,
            sharpe_ratio=1.5, n_trades=30, win_rate=0.6,
            created_at=datetime.now(),
            trades=[]
        )
        assert result.total_return == 0.15
        assert result.win_rate == 0.6

    def test_backtest_summary_response(self):
        summary = schemas.BacktestSummaryResponse(
            id=1, name="摘要", strategy_type="ml",
            market="A", status="completed",
            initial_capital=1_000_000,
            created_at=datetime.now()
        )
        # 摘要不包含 trades 字段
        assert not hasattr(summary, 'trades')


# ========== 回测服务层测试 ==========
class TestMockDailyValues:
    def test_generate_daily_values(self):
        values = _generate_mock_daily_values(
            initial_capital=1_000_000, n_days=60, seed=42
        )
        assert len(values) == 61  # 60 天 + 初始日
        assert values[0]["total_value"] == 1_000_000
        # 每条都有必要字段
        for v in values:
            assert "date" in v
            assert "cash" in v
            assert "holdings_value" in v
            assert "total_value" in v
            assert "daily_return" in v
            assert "drawdown" in v

    def test_daily_values_drawdown(self):
        values = _generate_mock_daily_values(
            initial_capital=1_000_000, n_days=30, seed=123
        )
        # 回撤应该 <= 0
        for v in values:
            assert v["drawdown"] <= 0.0001  # 允许浮点误差

    def test_daily_values_different_seeds(self):
        v1 = _generate_mock_daily_values(1_000_000, 30, seed=1)
        v2 = _generate_mock_daily_values(1_000_000, 30, seed=2)
        assert v1[10]["total_value"] != v2[10]["total_value"]


class TestMockTrades:
    def test_generate_trades(self):
        trades = _generate_mock_trades(
            n_trades=10, codes=["600519.SH", "000858.SZ"], seed=42
        )
        # 每笔交易有买入+卖出 = 20 条
        assert len(trades) == 20
        # 买入和卖出数量相等
        buys = [t for t in trades if t["action"] == "buy"]
        sells = [t for t in trades if t["action"] == "sell"]
        assert len(buys) == 10
        assert len(sells) == 10

    def test_trade_fields(self):
        trades = _generate_mock_trades(
            n_trades=1, codes=["600519.SH"], seed=42
        )
        buy = [t for t in trades if t["action"] == "buy"][0]
        assert "date" in buy
        assert "code" in buy
        assert "price" in buy
        assert "shares" in buy
        assert "commission" in buy

    def test_sell_has_pnl(self):
        trades = _generate_mock_trades(
            n_trades=5, codes=["000001.SZ"], seed=99
        )
        sells = [t for t in trades if t["action"] == "sell"]
        for s in sells:
            assert "pnl" in s
            assert "pnl_pct" in s
            assert "stamp_tax" in s


class TestMockFeatureImportance:
    def test_generate_features(self):
        features = _generate_mock_feature_importance(n_features=8, seed=42)
        assert len(features) == 8
        # 已按重要性降序排列
        for i in range(len(features) - 1):
            assert features[i]["importance"] >= features[i + 1]["importance"]

    def test_feature_fields(self):
        features = _generate_mock_feature_importance(seed=42)
        for f in features:
            assert "feature" in f
            assert "importance" in f
            assert 0 < f["importance"] < 1


class TestRunBacktest:
    def test_run_backtest_success(self, db_session):
        config = schemas.BacktestConfig(name="单元测试回测")
        result = run_backtest(db_session, config)

        assert result.id is not None
        assert result.name == "单元测试回测"
        assert result.status == "completed"
        assert result.initial_capital == 1_000_000
        assert result.final_value is not None
        assert result.total_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None
        assert result.n_trades > 0
        assert result.daily_values is not None
        assert result.feature_importance is not None

    def test_run_backtest_creates_trades(self, db_session):
        config = schemas.BacktestConfig(name="交易测试")
        result = run_backtest(db_session, config)

        trades = db_session.query(models.BacktestTrade).filter(
            models.BacktestTrade.backtest_id == result.id
        ).all()
        assert len(trades) > 0
        # 有买入和卖出
        actions = set(t.action for t in trades)
        assert "buy" in actions
        assert "sell" in actions

    def test_run_backtest_daily_values_valid_json(self, db_session):
        config = schemas.BacktestConfig(name="JSON测试")
        result = run_backtest(db_session, config)

        daily = json.loads(result.daily_values)
        assert isinstance(daily, list)
        assert len(daily) > 0
        assert "total_value" in daily[0]
        assert "drawdown" in daily[0]

    def test_run_backtest_feature_importance_valid_json(self, db_session):
        config = schemas.BacktestConfig(name="特征测试")
        result = run_backtest(db_session, config)

        features = json.loads(result.feature_importance)
        assert isinstance(features, list)
        assert len(features) > 0
        assert "feature" in features[0]
        assert "importance" in features[0]

    def test_run_backtest_custom_params(self, db_session):
        config = schemas.BacktestConfig(
            name="自定义参数",
            initial_capital=500_000,
            commission=0.001,
            stamp_tax=0.002,
            slippage=0.002,
        )
        result = run_backtest(db_session, config)
        assert result.initial_capital == 500_000
        assert result.commission == 0.001
        assert result.stamp_tax == 0.002
        assert result.slippage == 0.002

    def test_run_backtest_different_names_different_results(self, db_session):
        r1 = run_backtest(db_session, schemas.BacktestConfig(name="回测A"))
        r2 = run_backtest(db_session, schemas.BacktestConfig(name="回测B"))
        # 不同名称产生不同 seed，结果应不同
        assert r1.final_value != r2.final_value


# ========== 回测 CRUD 测试 ==========
class TestBacktestCRUD:
    def test_create_and_get(self, db_session):
        result = models.BacktestResult(
            name="CRUD测试", strategy_type="test",
            market=models.MarketType.A, status="completed",
            initial_capital=1_000_000,
        )
        db_session.add(result)
        db_session.commit()
        db_session.refresh(result)

        found = db_session.query(models.BacktestResult).filter(
            models.BacktestResult.id == result.id
        ).first()
        assert found is not None
        assert found.name == "CRUD测试"

    def test_delete_backtest(self, db_session):
        result = models.BacktestResult(
            name="删除测试", strategy_type="test",
            market=models.MarketType.A, status="completed",
            initial_capital=1_000_000,
        )
        db_session.add(result)
        db_session.commit()

        db_session.delete(result)
        db_session.commit()

        found = db_session.query(models.BacktestResult).filter(
            models.BacktestResult.id == result.id
        ).first()
        assert found is None

    def test_backtest_trade_relationship(self, db_session):
        result = models.BacktestResult(
            name="关联测试", strategy_type="test",
            market=models.MarketType.A, status="completed",
            initial_capital=1_000_000,
        )
        db_session.add(result)
        db_session.flush()

        trade = models.BacktestTrade(
            backtest_id=result.id, date="2024-01-15",
            action="buy", code="600519.SH",
            price=1800.0, shares=100, cost=180030.0,
        )
        db_session.add(trade)
        db_session.commit()

        found = db_session.query(models.BacktestResult).filter(
            models.BacktestResult.id == result.id
        ).first()
        assert len(found.trades) == 1
        assert found.trades[0].code == "600519.SH"
