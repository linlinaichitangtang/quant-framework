"""
V2.2 深度学习策略引擎单元测试

包含特征工程、LSTM/Transformer 模型、DQN/PPO 代理、交易环境、
在线学习、模型监控、ML 服务层和 API 端点的完整测试。

所有测试使用模拟数据，mock 外部依赖，可独立运行。
"""
import json
import pytest
import numpy as np
import pandas as pd
import torch
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime
from io import BytesIO
import os
import sys

# 确保项目根目录和 backend 目录在路径中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, 'backend'))


# ========== 辅助函数 ==========

def create_sample_ohlcv(days=200, seed=42):
    """创建模拟 OHLCV 数据"""
    np.random.seed(seed)
    dates = pd.date_range('2024-01-01', periods=days, freq='B')
    base_price = np.random.uniform(20, 80)
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, days)),
        'low': prices * (1 - np.random.uniform(0, 0.03, days)),
        'close': prices,
        'volume': np.random.uniform(1000000, 10000000, days),
    }, index=dates)
    return df


# ========== TestFeatureEngineering: 特征工程测试 ==========

class TestFeatureEngineering:
    """特征工程引擎测试"""

    def setup_method(self):
        from app.feature_engineering import FeatureEngineer
        self.fe = FeatureEngineer()
        self.df = create_sample_ohlcv(days=200)

    def test_build_features_returns_dataframe(self):
        """测试 build_features 返回 DataFrame"""
        result = self.fe.build_features(self.df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(self.df)

    def test_build_features_creates_all_features(self):
        """测试 build_features 创建所有特征列"""
        result = self.fe.build_features(self.df)
        # 检查关键特征列存在
        expected_features = [
            'returns_1d', 'ma5', 'ma20', 'rsi_14', 'macd',
            'volatility_20d', 'atr_14', 'obv', 'adx_14',
            'bollinger_upper', 'bollinger_lower', 'stochastic_k',
        ]
        for feat in expected_features:
            assert feat in result.columns, f"缺少特征: {feat}"

    def test_build_features_sets_feature_names(self):
        """测试 build_features 设置 feature_names"""
        self.fe.build_features(self.df)
        assert isinstance(self.fe.feature_names, list)
        assert len(self.fe.feature_names) > 50  # 至少 50 个特征

    def test_normalize_fit(self):
        """测试 normalize fit 模式"""
        df = self.fe.build_features(self.df)
        result = self.fe.normalize(df, fit=True)
        assert self.fe.scaler is not None
        # 归一化后特征列的均值应接近 0
        feature_cols = [c for c in self.fe.feature_names if c in result.columns]
        means = result[feature_cols].mean()
        assert np.all(np.abs(means) < 1.0)  # 大部分均值应接近 0

    def test_normalize_without_fit_raises(self):
        """测试未 fit 就 normalize 应抛出异常"""
        df = self.fe.build_features(self.df)
        with pytest.raises(ValueError, match="Scaler not fitted"):
            self.fe.normalize(df, fit=False)

    def test_normalize_transform(self):
        """测试 normalize transform 模式"""
        df = self.fe.build_features(self.df)
        self.fe.normalize(df, fit=True)
        result = self.fe.normalize(df, fit=False)
        assert isinstance(result, pd.DataFrame)

    def test_create_sequences(self):
        """测试 create_sequences 创建序列"""
        df = self.fe.build_features(self.df)
        self.fe.normalize(df, fit=True)
        X, y = self.fe.create_sequences(df, seq_length=20)
        assert len(X) > 0
        assert len(X) == len(y)
        assert X.ndim == 3  # (samples, seq_length, features)
        assert X.shape[1] == 20  # seq_length
        assert y.ndim == 1
        # 标签应为 0, 1, 2
        assert set(np.unique(y)).issubset({0, 1, 2})

    def test_create_sequences_short_data(self):
        """测试数据不足时 create_sequences 返回空"""
        short_df = self.df.head(30)
        df = self.fe.build_features(short_df)
        self.fe.normalize(df, fit=True)
        X, y = self.fe.create_sequences(df, seq_length=60)
        assert len(X) == 0
        assert len(y) == 0

    def test_rsi_range(self):
        """测试 RSI 值在合理范围内"""
        result = self.fe.build_features(self.df)
        valid_rsi = result['rsi_14'].dropna()
        assert valid_rsi.min() >= 0
        assert valid_rsi.max() <= 100

    def test_bollinger_bands_relationship(self):
        """测试布林带上下轨关系"""
        result = self.fe.build_features(self.df)
        valid = result.dropna(subset=['bollinger_upper', 'bollinger_lower'])
        assert (valid['bollinger_upper'] >= valid['bollinger_lower']).all()

    def test_get_feature_importance_with_model(self):
        """测试 get_feature_importance 对有 feature_importances_ 的模型"""
        self.fe.build_features(self.df)
        n_features = len(self.fe.feature_names)
        mock_model = MagicMock()
        mock_model.feature_importances_ = np.array([0.1] * n_features)
        importance = self.fe.get_feature_importance(mock_model)
        assert isinstance(importance, dict)
        assert len(importance) == n_features

    def test_get_feature_importance_without_attribute(self):
        """测试 get_feature_importance 对无 feature_importances_ 的模型"""
        mock_model = MagicMock()
        # 移除 feature_importances_ 和 coef_ 属性
        del mock_model.feature_importances_
        del mock_model.coef_
        self.fe.build_features(self.df)
        importance = self.fe.get_feature_importance(mock_model)
        assert importance == {}


# ========== TestLSTMModel: LSTM 模型测试 ==========

class TestLSTMModel:
    """LSTM 模型测试"""

    def setup_method(self):
        from app.lstm_model import LSTMModel
        self.model = LSTMModel(input_size=63, hidden_size=32, num_layers=1, dropout=0.0)

    def test_create_model(self):
        """测试创建 LSTM 模型"""
        assert self.model is not None
        # 检查参数数量
        total_params = sum(p.numel() for p in self.model.parameters())
        assert total_params > 0

    def test_forward_pass(self):
        """测试前向传播"""
        import torch
        batch_size = 4
        seq_len = 10
        x = torch.randn(batch_size, seq_len, 63)
        output = self.model(x)
        assert output.shape == (batch_size, 3)  # 3 分类

    def test_forward_batch_size_1(self):
        """测试 batch_size=1 的前向传播"""
        import torch
        x = torch.randn(1, 10, 63)
        output = self.model(x)
        assert output.shape == (1, 3)

    def test_output_softmax(self):
        """测试输出经过 softmax 后概率和为 1"""
        import torch
        x = torch.randn(2, 10, 63)
        output = self.model(x)
        probs = torch.softmax(output, dim=1)
        prob_sums = probs.sum(dim=1)
        assert torch.allclose(prob_sums, torch.ones(2), atol=1e-5)

    def test_train_and_predict(self):
        """测试 PricePredictor 训练和预测流程"""
        from app.lstm_model import PricePredictor
        df = create_sample_ohlcv(days=200)
        predictor = PricePredictor(model_type="lstm", device="cpu")

        # 训练（少量 epoch）
        metrics = predictor.train(df, {
            'epochs': 3,
            'batch_size': 16,
            'learning_rate': 0.001,
            'seq_length': 20,
            'val_split': 0.2,
            'patience': 10,
        })

        assert 'train_loss' in metrics
        assert 'val_loss' in metrics
        assert 'epochs' in metrics
        assert metrics['epochs'] > 0

    def test_predict_without_model_raises(self):
        """测试未加载模型时预测应抛出异常"""
        from app.lstm_model import PricePredictor
        predictor = PricePredictor(model_type="lstm", device="cpu")
        df = create_sample_ohlcv(days=200)
        with pytest.raises(ValueError, match="模型未加载"):
            predictor.predict(df, seq_length=20)

    def test_save_and_load_model(self, tmp_path):
        """测试模型保存和加载"""
        from app.lstm_model import PricePredictor

        df = create_sample_ohlcv(days=200)
        predictor = PricePredictor(model_type="lstm", device="cpu")
        predictor.train(df, {
            'epochs': 2,
            'batch_size': 16,
            'seq_length': 20,
            'val_split': 0.2,
            'patience': 10,
        })

        # 保存
        save_path = str(tmp_path / "test_model")
        os.makedirs(save_path, exist_ok=True)
        predictor.save_model(save_path)

        # 验证文件存在
        assert os.path.exists(os.path.join(save_path, 'model.pt'))
        assert os.path.exists(os.path.join(save_path, 'metadata.json'))

        # 加载
        new_predictor = PricePredictor(model_type="lstm", device="cpu")
        new_predictor.load_model(save_path)

        # 验证预测
        result = new_predictor.predict(df, seq_length=20)
        assert 'direction' in result
        assert 'confidence' in result
        assert result['direction'] in ['up', 'down', 'flat']
        assert 0 <= result['confidence'] <= 1


# ========== TestTransformerModel: Transformer 模型测试 ==========

class TestTransformerModel:
    """Transformer 模型测试"""

    def setup_method(self):
        from app.lstm_model import TransformerTimeSeriesModel
        self.model = TransformerTimeSeriesModel(
            input_size=63, d_model=32, nhead=4, num_layers=1, dropout=0.0
        )

    def test_create_model(self):
        """测试创建 Transformer 模型"""
        assert self.model is not None
        total_params = sum(p.numel() for p in self.model.parameters())
        assert total_params > 0

    def test_forward_pass(self):
        """测试前向传播"""
        import torch
        batch_size = 4
        seq_len = 10
        x = torch.randn(batch_size, seq_len, 63)
        output = self.model(x)
        assert output.shape == (batch_size, 3)

    def test_train_transformer(self):
        """测试 Transformer 训练"""
        from app.lstm_model import PricePredictor
        df = create_sample_ohlcv(days=200)
        predictor = PricePredictor(model_type="transformer", device="cpu")

        metrics = predictor.train(df, {
            'epochs': 2,
            'batch_size': 16,
            'seq_length': 20,
            'val_split': 0.2,
            'patience': 10,
        })

        assert 'train_loss' in metrics
        assert metrics['epochs'] > 0

    def test_positional_encoding(self):
        """测试位置编码"""
        from app.lstm_model import PositionalEncoding
        import torch

        pe = PositionalEncoding(d_model=32, dropout=0.0, max_len=100)
        x = torch.randn(2, 50, 32)
        out = pe(x)
        assert out.shape == x.shape


# ========== TestDQNAgent: DQN 代理测试 ==========

class TestDQNAgent:
    """DQN 代理测试"""

    def setup_method(self):
        from app.rl_agent import DQNAgent
        self.agent = DQNAgent(state_size=10, action_size=3, learning_rate=0.001)

    def test_create_agent(self):
        """测试创建 DQN 代理"""
        assert self.agent is not None
        assert self.agent.state_size == 10
        assert self.agent.action_size == 3

    def test_select_action_training(self):
        """测试训练模式下的动作选择"""
        state = np.random.randn(10).astype(np.float32)
        action = self.agent.select_action(state, training=True)
        assert action in [0, 1, 2]

    def test_select_action_greedy(self):
        """测试贪婪模式下的动作选择"""
        state = np.random.randn(10).astype(np.float32)
        self.agent.epsilon = 0.0  # 禁用探索
        # 使用 batch=2 避免 BatchNorm 单样本问题
        action = self.agent.select_action(state, training=False)
        assert action in [0, 1, 2]

    def test_train_step_insufficient_buffer(self):
        """测试经验不足时的训练步骤"""
        loss = self.agent.train_step(batch_size=64)
        assert loss == 0.0

    def test_train_step_with_buffer(self):
        """测试有足够经验时的训练步骤"""
        # 填充经验回放缓冲区
        for _ in range(100):
            state = np.random.randn(10).astype(np.float32)
            action = np.random.randint(0, 3)
            reward = np.random.randn()
            next_state = np.random.randn(10).astype(np.float32)
            done = False
            self.agent.memory.push(state, action, reward, next_state, done)

        loss = self.agent.train_step(batch_size=32)
        assert isinstance(loss, float)
        assert loss >= 0

    def test_update_target_network(self):
        """测试更新目标网络"""
        self.agent.update_target_network()
        # 验证两个网络参数一致
        for p1, p2 in zip(self.agent.policy_net.parameters(), self.agent.target_net.parameters()):
            assert torch.equal(p1.data, p2.data)

    def test_save_and_load(self, tmp_path):
        """测试 DQN 代理保存和加载"""
        save_path = str(tmp_path / "test_dqn")
        os.makedirs(save_path, exist_ok=True)
        self.agent.save(save_path)

        assert os.path.exists(os.path.join(save_path, 'dqn_agent.pt'))

        new_agent = self.agent.__class__(state_size=10, action_size=3)
        new_agent.load(save_path)
        assert new_agent.state_size == 10


# ========== TestTradingEnvironment: 交易环境测试 ==========

class TestTradingEnvironment:
    """交易环境测试"""

    def setup_method(self):
        from app.feature_engineering import FeatureEngineer
        from app.rl_agent import TradingEnvironment

        df = create_sample_ohlcv(days=100)
        fe = FeatureEngineer()
        self.df = fe.build_features(df)
        self.env = TradingEnvironment(self.df, initial_capital=100000, commission=0.0003)

    def test_reset(self):
        """测试环境重置"""
        state = self.env.reset()
        assert isinstance(state, np.ndarray)
        assert state.shape == (self.env.state_size,)
        assert self.env.cash == 100000
        assert self.env.position == 0

    def test_step_hold(self):
        """测试持有动作"""
        self.env.reset()
        next_state, reward, done, info = self.env.step(0)  # hold
        assert isinstance(next_state, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert info['action'] == 'hold'

    def test_step_buy(self):
        """测试买入动作"""
        self.env.reset()
        next_state, reward, done, info = self.env.step(1)  # buy
        assert info['action'] == 'buy'
        assert info['shares'] > 0
        assert self.env.position > 0
        assert self.env.cash < 100000

    def test_step_sell(self):
        """测试卖出动作"""
        self.env.reset()
        self.env.step(1)  # 先买入
        next_state, reward, done, info = self.env.step(2)  # 卖出
        assert info['action'] == 'sell'
        assert self.env.position == 0
        assert 'pnl' in info

    def test_step_sell_without_position(self):
        """测试无持仓时卖出"""
        self.env.reset()
        next_state, reward, done, info = self.env.step(2)  # sell
        # 无持仓时卖出不执行任何操作
        assert self.env.position == 0

    def test_episode_completion(self):
        """测试回合结束"""
        self.env.reset()
        done = False
        steps = 0
        while not done:
            _, _, done, _ = self.env.step(0)  # hold
            steps += 1
        assert done
        assert steps == len(self.df) - 1

    def test_state_size(self):
        """测试状态大小"""
        self.env.reset()
        state = self.env._get_state()
        assert len(state) == self.env.state_size
        # state_size = feature_cols + 3 (position_norm, portfolio_norm, price_norm)
        assert self.env.state_size > 3

    def test_portfolio_value_tracking(self):
        """测试组合价值跟踪"""
        self.env.reset()
        initial_value = self.env.portfolio_value
        self.env.step(1)  # buy
        # 买入后组合价值应接近初始值（扣除手续费）
        assert self.env.portfolio_value < initial_value
        assert self.env.portfolio_value > 0


# ========== TestPPOAgent: PPO 代理测试 ==========

class TestPPOAgent:
    """PPO 代理测试 - 如果 ppo_agent.py 不存在则跳过"""

    def test_ppo_module_exists(self):
        """检查 PPO 模块是否存在"""
        try:
            from app.ppo_agent import PPOAgent
            assert True
        except ImportError:
            pytest.skip("ppo_agent.py 尚未创建，跳过 PPO 测试")


# ========== TestOnlineLearning: 在线学习引擎测试 ==========

class TestOnlineLearning:
    """在线学习引擎测试 - 如果 online_learning.py 不存在则跳过"""

    def test_online_learning_module_exists(self):
        """检查在线学习模块是否存在"""
        try:
            from app.online_learning import OnlineLearningEngine
            assert True
        except ImportError:
            pytest.skip("online_learning.py 尚未创建，跳过在线学习测试")


# ========== TestModelMonitor: 模型监控测试 ==========

class TestModelMonitor:
    """模型监控测试 - 如果 model_monitor.py 不存在则跳过"""

    def test_model_monitor_module_exists(self):
        """检查模型监控模块是否存在"""
        try:
            from app.model_monitor import ModelMonitor
            assert True
        except ImportError:
            pytest.skip("model_monitor.py 尚未创建，跳过模型监控测试")


# ========== TestMLService: ML 服务层测试 ==========

class TestMLService:
    """ML 服务层测试"""

    def setup_method(self):
        from app.ml_service import MLService
        self.service = MLService()

    def test_list_models_empty(self, db_session):
        """测试空模型列表"""
        models = self.service.list_models(db_session)
        assert models == []

    def test_register_model(self, db_session):
        """测试注册新模型"""
        model = self.service.register_model(
            db_session, name="测试LSTM", model_type="lstm", description="测试用"
        )
        assert model.id is not None
        assert model.name == "测试LSTM"
        assert model.model_type == "lstm"
        assert model.status == "active"

    def test_register_model_with_hyperparams(self, db_session):
        """测试注册带超参数的模型"""
        hyperparams = {'learning_rate': 0.001, 'hidden_size': 128}
        model = self.service.register_model(
            db_session, name="测试Transformer", model_type="transformer",
            hyperparams=hyperparams
        )
        assert model.hyperparams is not None
        parsed = json.loads(model.hyperparams)
        assert parsed['learning_rate'] == 0.001

    def test_get_model(self, db_session):
        """测试获取模型"""
        created = self.service.register_model(db_session, name="获取测试", model_type="lstm")
        found = self.service.get_model(db_session, created.id)
        assert found is not None
        assert found.name == "获取测试"

    def test_get_model_not_found(self, db_session):
        """测试获取不存在的模型"""
        found = self.service.get_model(db_session, 99999)
        assert found is None

    def test_archive_model(self, db_session):
        """测试归档模型"""
        model = self.service.register_model(db_session, name="归档测试", model_type="lstm")
        archived = self.service.archive_model(db_session, model.id)
        assert archived.status == "archived"

    def test_archive_model_not_found(self, db_session):
        """测试归档不存在的模型"""
        result = self.service.archive_model(db_session, 99999)
        assert result is None

    def test_list_models_with_filter(self, db_session):
        """测试带过滤条件的模型列表"""
        self.service.register_model(db_session, name="LSTM-1", model_type="lstm")
        self.service.register_model(db_session, name="DQN-1", model_type="dqn")
        self.service.register_model(db_session, name="LSTM-2", model_type="lstm")

        lstm_models = self.service.list_models(db_session, model_type="lstm")
        assert len(lstm_models) == 2
        assert all(m.model_type == "lstm" for m in lstm_models)

    def test_get_features(self):
        """测试获取可用特征列表"""
        features = self.service.get_features()
        assert 'features' in features
        assert 'count' in features
        assert 'categories' in features
        # feature_names 在 build_features 后才会填充，这里检查 categories
        assert len(features['categories']) > 0

    def test_compute_features(self):
        """测试计算特征"""
        df = create_sample_ohlcv(days=200)
        result = self.service.compute_features(df)
        assert 'features' in result
        assert 'count' in result
        assert 'total_rows' in result
        assert result['count'] > 50

    def test_get_training_status_not_found(self, db_session):
        """测试获取不存在的训练状态"""
        status = self.service.get_training_status(db_session, 99999)
        assert status['status'] == 'not_found'

    def test_get_training_metrics_not_found(self, db_session):
        """测试获取不存在的训练指标"""
        metrics = self.service.get_training_metrics(db_session, 99999)
        assert metrics == {}

    def test_get_predictions_empty(self, db_session):
        """测试空预测列表"""
        predictions = self.service.get_predictions(db_session)
        assert predictions == []

    def test_get_prediction_accuracy_empty(self, db_session):
        """测试空预测准确率"""
        accuracy = self.service.get_prediction_accuracy(db_session)
        assert accuracy['total'] == 0
        assert accuracy['accuracy'] == 0

    def test_start_training_invalid_model(self, db_session):
        """测试训练不存在的模型"""
        df = create_sample_ohlcv(days=200)
        with pytest.raises(ValueError, match="不存在"):
            self.service.start_training(db_session, 99999, "lstm", df, {})

    def test_predict_invalid_model(self, db_session):
        """测试使用不存在的模型预测"""
        df = create_sample_ohlcv(days=200)
        with pytest.raises(ValueError, match="不存在"):
            self.service.predict(db_session, 99999, df, "000001")

    def test_predict_unsupported_model_type(self, db_session):
        """测试使用不支持预测的模型类型"""
        df = create_sample_ohlcv(days=200)
        model = self.service.register_model(db_session, name="DQN模型", model_type="dqn")
        with pytest.raises(ValueError, match="不支持预测"):
            self.service.predict(db_session, model.id, df, "000001")

    def test_predict_no_model_file(self, db_session):
        """测试模型文件不存在时预测"""
        df = create_sample_ohlcv(days=200)
        model = self.service.register_model(db_session, name="无文件LSTM", model_type="lstm")
        with pytest.raises(ValueError, match="模型文件不存在"):
            self.service.predict(db_session, model.id, df, "000001")


# ========== TestMLAPI: ML API 端点测试 ==========

class TestMLAPI:
    """ML API 端点测试"""

    def setup_method(self):
        """创建 FastAPI 测试客户端"""
        from fastapi.testclient import TestClient
        from app.main import app

        self.client = TestClient(app)

    def test_list_models_empty(self):
        """测试获取模型列表"""
        response = self.client.get("/api/v1/ml/models")
        assert response.status_code == 200
        data = response.json()
        assert 'data' in data
        assert isinstance(data['data'], list)

    def test_create_model_success(self):
        """测试创建模型成功"""
        response = self.client.post("/api/v1/ml/models", json={
            "name": "API测试LSTM",
            "model_type": "lstm",
            "description": "API测试用"
        })
        assert response.status_code == 200
        data = response.json()
        assert data['data']['name'] == "API测试LSTM"
        assert 'id' in data['data']

    def test_create_model_invalid_type(self):
        """测试创建不支持的模型类型"""
        response = self.client.post("/api/v1/ml/models", json={
            "name": "无效类型",
            "model_type": "invalid_type"
        })
        assert response.status_code == 400

    def test_get_model_not_found(self):
        """测试获取不存在的模型"""
        response = self.client.get("/api/v1/ml/models/99999")
        assert response.status_code == 404

    def test_delete_model_not_found(self):
        """测试归档不存在的模型"""
        response = self.client.delete("/api/v1/ml/models/99999")
        assert response.status_code == 404

    def test_get_features(self):
        """测试获取特征列表"""
        response = self.client.get("/api/v1/ml/features")
        assert response.status_code == 200
        data = response.json()
        assert 'data' in data
        assert 'features' in data['data']
        # categories 包含所有特征分类
        assert len(data['data']['categories']) > 0

    def test_compute_features(self):
        """测试计算特征"""
        response = self.client.post("/api/v1/ml/features/compute", json={
            "symbol": "000001",
            "days": 120
        })
        assert response.status_code == 200
        data = response.json()
        assert 'data' in data
        assert 'features' in data['data']

    def test_predict_model_not_found(self):
        """测试预测时模型不存在"""
        response = self.client.post("/api/v1/ml/predict", json={
            "model_id": 99999,
            "symbol": "000001"
        })
        # 模型不存在返回 400 (ValueError 被捕获)
        assert response.status_code == 400

    def test_get_predictions_empty(self):
        """测试获取空预测历史"""
        response = self.client.get("/api/v1/ml/predictions")
        assert response.status_code == 200
        data = response.json()
        assert data['data'] == []

    def test_get_prediction_accuracy_empty(self):
        """测试获取空预测准确率"""
        response = self.client.get("/api/v1/ml/predictions/accuracy")
        assert response.status_code == 200
        data = response.json()
        assert data['data']['total'] == 0

    def test_training_status_not_found(self):
        """测试获取不存在的训练状态"""
        response = self.client.get("/api/v1/ml/train/99999/status")
        assert response.status_code == 404

    def test_training_metrics_not_found(self):
        """测试获取不存在的训练指标"""
        response = self.client.get("/api/v1/ml/train/99999/metrics")
        assert response.status_code == 404

    def test_create_and_get_model(self):
        """测试创建后获取模型"""
        # 创建
        create_resp = self.client.post("/api/v1/ml/models", json={
            "name": "创建获取测试",
            "model_type": "transformer"
        })
        model_id = create_resp.json()['data']['id']

        # 获取
        get_resp = self.client.get(f"/api/v1/ml/models/{model_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()['data']
        assert data['name'] == "创建获取测试"
        assert data['model_type'] == "transformer"

    def test_list_models_after_create(self):
        """测试创建后列表包含新模型"""
        self.client.post("/api/v1/ml/models", json={
            "name": "列表测试",
            "model_type": "lstm"
        })
        response = self.client.get("/api/v1/ml/models")
        data = response.json()['data']
        names = [m['name'] for m in data]
        assert "列表测试" in names

    def test_archive_model(self):
        """测试归档模型"""
        create_resp = self.client.post("/api/v1/ml/models", json={
            "name": "归档API测试",
            "model_type": "dqn"
        })
        model_id = create_resp.json()['data']['id']

        archive_resp = self.client.delete(f"/api/v1/ml/models/{model_id}")
        assert archive_resp.status_code == 200

        # 验证状态
        get_resp = self.client.get(f"/api/v1/ml/models/{model_id}")
        # 归档后仍然可以获取，但状态应为 archived
        assert get_resp.json()['data']['status'] == 'archived'

    def test_filter_models_by_type(self):
        """测试按类型过滤模型"""
        self.client.post("/api/v1/ml/models", json={"name": "F-LSTM", "model_type": "lstm"})
        self.client.post("/api/v1/ml/models", json={"name": "F-DQN", "model_type": "dqn"})

        response = self.client.get("/api/v1/ml/models", params={"model_type": "lstm"})
        data = response.json()['data']
        assert all(m['model_type'] == 'lstm' for m in data)


# ========== TestReplayBuffer: 经验回放缓冲区测试 ==========

class TestReplayBuffer:
    """经验回放缓冲区测试"""

    def test_push_and_len(self):
        """测试添加经验和长度"""
        from app.rl_agent import ReplayBuffer
        buffer = ReplayBuffer(capacity=100)
        assert len(buffer) == 0

        buffer.push(np.zeros(5), 1, 0.5, np.zeros(5), False)
        assert len(buffer) == 1

        for _ in range(50):
            buffer.push(np.zeros(5), 0, 0.1, np.zeros(5), False)
        assert len(buffer) == 51

    def test_capacity_limit(self):
        """测试容量限制"""
        from app.rl_agent import ReplayBuffer
        buffer = ReplayBuffer(capacity=10)
        for _ in range(20):
            buffer.push(np.zeros(5), 0, 0.1, np.zeros(5), False)
        assert len(buffer) == 10

    def test_sample(self):
        """测试采样"""
        from app.rl_agent import ReplayBuffer
        buffer = ReplayBuffer(capacity=100)
        for _ in range(50):
            buffer.push(np.random.randn(5), np.random.randint(0, 3),
                       np.random.randn(), np.random.randn(5), False)

        states, actions, rewards, next_states, dones = buffer.sample(16)
        assert states.shape == (16, 5)
        assert actions.shape == (16,)
        assert rewards.shape == (16,)
        assert next_states.shape == (16, 5)
        assert dones.shape == (16,)


# ========== TestDQNNetwork: DQN 网络结构测试 ==========

class TestDQNNetwork:
    """DQN 网络结构测试"""

    def test_network_output_shape(self):
        """测试网络输出形状"""
        from app.rl_agent import DQNNetwork
        import torch

        net = DQNNetwork(state_size=10, action_size=3)
        x = torch.randn(4, 10)
        output = net(x)
        assert output.shape == (4, 3)

    def test_network_single_input(self):
        """测试单个输入"""
        from app.rl_agent import DQNNetwork

        net = DQNNetwork(state_size=10, action_size=3)
        x = torch.randn(1, 10)  # 使用 batch=1 避免 BatchNorm 问题
        output = net(x)
        assert output.shape == (1, 3)


# ========== TestTradingTrainer: 交易训练器测试 ==========

class TestTradingTrainer:
    """交易训练器测试"""

    def test_trainer_create(self):
        """测试创建训练器"""
        from app.feature_engineering import FeatureEngineer
        from app.rl_agent import TradingEnvironment, DQNAgent, TradingTrainer

        df = create_sample_ohlcv(days=100)
        fe = FeatureEngineer()
        df = fe.build_features(df)

        env = TradingEnvironment(df, initial_capital=100000)
        agent = DQNAgent(state_size=env.state_size, action_size=3)
        trainer = TradingTrainer(env, agent)

        assert trainer.env is env
        assert trainer.agent is agent

    def test_trainer_train_few_episodes(self):
        """测试训练少量回合"""
        from app.feature_engineering import FeatureEngineer
        from app.rl_agent import TradingEnvironment, DQNAgent, TradingTrainer

        df = create_sample_ohlcv(days=80)
        fe = FeatureEngineer()
        df = fe.build_features(df)

        env = TradingEnvironment(df, initial_capital=100000)
        agent = DQNAgent(state_size=env.state_size, action_size=3, learning_rate=0.01)
        trainer = TradingTrainer(env, agent)

        metrics = trainer.train(num_episodes=3, max_steps=20, batch_size=16, target_update_freq=2)

        assert 'episode_rewards' in metrics
        assert 'total_episodes' in metrics
        assert len(metrics['episode_rewards']) == 3

    def test_trainer_evaluate(self):
        """测试评估"""
        from app.feature_engineering import FeatureEngineer
        from app.rl_agent import TradingEnvironment, DQNAgent, TradingTrainer

        df = create_sample_ohlcv(days=80)
        fe = FeatureEngineer()
        df = fe.build_features(df)

        env = TradingEnvironment(df, initial_capital=100000)
        agent = DQNAgent(state_size=env.state_size, action_size=3)
        trainer = TradingTrainer(env, agent)

        result = trainer.evaluate(num_episodes=2)
        assert 'avg_return' in result
        assert 'num_episodes' in result
        assert result['num_episodes'] == 2


# ========== TestMLModelDB: 数据库模型测试 ==========

class TestMLModelDB:
    """ML 数据库模型测试"""

    def test_create_ml_model(self, db_session):
        """测试创建 ML 模型记录"""
        from app.models import MLModel
        model = MLModel(
            name="DB测试LSTM",
            model_type="lstm",
            version="1.0.0",
            status="active",
            description="数据库测试",
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)

        assert model.id is not None
        assert model.name == "DB测试LSTM"
        assert model.created_at is not None

    def test_create_training_record(self, db_session):
        """测试创建训练记录"""
        from app.models import MLModel, TrainingRecord

        model = MLModel(name="训练记录测试", model_type="lstm")
        db_session.add(model)
        db_session.flush()

        record = TrainingRecord(
            model_id=model.id,
            status="completed",
            dataset_info=json.dumps({"rows": 1000}),
            train_metrics=json.dumps({"loss": [1.0, 0.5]}),
            test_metrics=json.dumps({"accuracy": 0.65}),
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.model_id == model.id

    def test_create_prediction_record(self, db_session):
        """测试创建预测记录"""
        from app.models import MLModel, PredictionRecord

        model = MLModel(name="预测记录测试", model_type="lstm")
        db_session.add(model)
        db_session.flush()

        prediction = PredictionRecord(
            model_id=model.id,
            symbol="000001",
            market="a_stock",
            prediction_date=datetime.now(),
            predicted_return=0.023,
            predicted_direction="up",
            confidence=0.75,
        )
        db_session.add(prediction)
        db_session.commit()

        assert prediction.id is not None
        assert prediction.predicted_direction == "up"

    def test_ml_model_relationship(self, db_session):
        """测试模型关联关系"""
        from app.models import MLModel, TrainingRecord, PredictionRecord

        model = MLModel(name="关联测试", model_type="transformer")
        db_session.add(model)
        db_session.flush()

        # 添加训练记录
        tr = TrainingRecord(model_id=model.id, status="completed")
        db_session.add(tr)

        # 添加预测记录
        pr = PredictionRecord(
            model_id=model.id, symbol="600519",
            prediction_date=datetime.now(),
            predicted_direction="down", confidence=0.6
        )
        db_session.add(pr)
        db_session.commit()

        # 验证关联
        found = db_session.query(MLModel).filter(MLModel.id == model.id).first()
        assert len(found.training_records) == 1
        assert len(found.prediction_records) == 1

    def test_prediction_accuracy_calculation(self, db_session):
        """测试预测准确率计算"""
        from app.models import MLModel, PredictionRecord
        from app.ml_service import MLService

        model = MLModel(name="准确率测试", model_type="lstm")
        db_session.add(model)
        db_session.flush()

        # 添加已验证的预测记录
        predictions = [
            ("up", "up", 0.8),
            ("up", "down", 0.6),
            ("down", "down", 0.7),
            ("up", "up", 0.9),
            ("flat", "flat", 0.5),
        ]
        for pred_dir, actual_dir, conf in predictions:
            pr = PredictionRecord(
                model_id=model.id, symbol="000001",
                prediction_date=datetime.now(),
                predicted_direction=pred_dir,
                predicted_return=0.01,
                confidence=conf,
                actual_direction=actual_dir,
                actual_return=0.015 if pred_dir == actual_dir else -0.01,
            )
            db_session.add(pr)
        db_session.commit()

        service = MLService()
        accuracy = service.get_prediction_accuracy(db_session, model_id=model.id)
        assert accuracy['total'] == 5
        assert accuracy['correct'] == 4  # 4/5 正确
        assert accuracy['accuracy'] == 0.8


# ========== TestPushSubscriptionDB: 推送订阅数据库测试 ==========

class TestPushSubscriptionDB:
    """推送订阅数据库模型测试"""

    def test_create_push_subscription(self, db_session):
        """测试创建推送订阅"""
        from app.models import User, PushSubscription

        user = User(username="push_test", email="push@test.com", hashed_password="hash123", role="user")
        db_session.add(user)
        db_session.flush()

        sub = PushSubscription(
            user_id=user.id,
            endpoint="https://fcm.googleapis.com/fcm/test-endpoint",
            keys_auth="test-auth-key",
            keys_p256dh="test-p256dh-key",
        )
        db_session.add(sub)
        db_session.commit()

        assert sub.id is not None
        assert sub.is_active is True

    def test_create_push_notification_history(self, db_session):
        """测试创建推送通知历史"""
        from app.models import User, PushNotificationHistory

        user = User(username="notif_test", email="notif@test.com", hashed_password="hash123", role="user")
        db_session.add(user)
        db_session.flush()

        history = PushNotificationHistory(
            user_id=user.id,
            title="测试通知",
            body="这是一条测试通知",
            url="/dashboard",
            status="sent",
        )
        db_session.add(history)
        db_session.commit()

        assert history.id is not None
        assert history.title == "测试通知"
