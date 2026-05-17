"""
ML 服务层 - V2.2 深度学习策略引擎

协调模型管理、训练和预测。
"""
import logging
import json
import threading
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any

from sqlalchemy.orm import Session
from .models import MLModel, TrainingRecord, PredictionRecord
from .feature_engineering import FeatureEngineer
from .lstm_model import PricePredictor
from .rl_agent import TradingEnvironment, DQNAgent, TradingTrainer
from .ppo_agent import PPOAgent, PPOTrainer
from .online_learning import OnlineLearningEngine
from .model_monitor import ModelMonitor
from .config import settings

logger = logging.getLogger(__name__)


class MLService:
    """ML 服务 - 模型管理、训练和预测"""

    def __init__(self):
        self._training_status: Dict[int, Dict] = {}  # record_id -> status dict
        self._training_threads: Dict[int, threading.Thread] = {}
        self._feature_engineer = FeatureEngineer()

        # 在线学习引擎
        self.online_learning = OnlineLearningEngine()
        self.online_learning.set_ml_service(self)

        # 模型监控
        self.model_monitor = ModelMonitor()

    # ========== 模型管理 ==========

    def list_models(self, db: Session, model_type: Optional[str] = None,
                    status: Optional[str] = None) -> List[MLModel]:
        """列出所有 ML 模型"""
        query = db.query(MLModel)
        if model_type:
            query = query.filter(MLModel.model_type == model_type)
        if status:
            query = query.filter(MLModel.status == status)
        return query.order_by(MLModel.created_at.desc()).all()

    def get_model(self, db: Session, model_id: int) -> Optional[MLModel]:
        """获取模型详情"""
        return db.query(MLModel).filter(MLModel.id == model_id).first()

    def register_model(self, db: Session, name: str, model_type: str,
                       description: Optional[str] = None,
                       hyperparams: Optional[Dict] = None) -> MLModel:
        """注册新模型"""
        model = MLModel(
            name=name,
            model_type=model_type,
            description=description,
            hyperparams=json.dumps(hyperparams, ensure_ascii=False) if hyperparams else None,
            status="active",
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    def archive_model(self, db: Session, model_id: int) -> Optional[MLModel]:
        """归档模型"""
        model = self.get_model(db, model_id)
        if model:
            model.status = "archived"
            db.commit()
            db.refresh(model)
        return model

    # ========== 训练 ==========

    def start_training(self, db: Session, model_id: int, model_type: str,
                       df, config: Dict) -> TrainingRecord:
        """启动模型训练（后台线程）"""
        model = self.get_model(db, model_id)
        if not model:
            raise ValueError(f"模型 ID {model_id} 不存在")

        # Create training record
        record = TrainingRecord(
            model_id=model_id,
            status="pending",
            dataset_info=json.dumps({
                'rows': len(df),
                'start': str(df.index[0]) if hasattr(df.index[0], 'strftime') else str(df.index[0]),
                'end': str(df.index[-1]) if hasattr(df.index[-1], 'strftime') else str(df.index[-1]),
            }, ensure_ascii=False),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Store training status in memory
        self._training_status[record.id] = {
            'status': 'pending',
            'progress': 0,
            'current_epoch': 0,
            'total_epochs': config.get('epochs', 100),
            'train_loss': [],
            'val_loss': [],
            'error': None,
        }

        # Start background training
        thread = threading.Thread(
            target=self._run_training,
            args=(record.id, model_id, model_type, df, config),
            daemon=True,
        )
        self._training_threads[record.id] = thread
        thread.start()

        return record

    def _run_training(self, record_id: int, model_id: int, model_type: str, df, config: Dict):
        """后台训练执行"""
        from .database import SessionLocal

        db = SessionLocal()
        try:
            # Update status
            record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
            record.status = "running"
            record.started_at = datetime.now()
            db.commit()

            self._training_status[record_id]['status'] = 'running'

            if model_type in ('lstm', 'transformer'):
                self._train_price_model(record_id, model_id, model_type, df, config, db)
            elif model_type == 'dqn':
                self._train_rl_agent(record_id, model_id, df, config, db)
            elif model_type == 'ppo':
                self._train_ppo_agent(record_id, model_id, df, config, db)
            else:
                raise ValueError(f"Unknown model type: {model_type}")

        except Exception as e:
            logger.error(f"训练失败 (record_id={record_id}): {e}", exc_info=True)
            record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
            if record:
                record.status = "failed"
                record.error_message = str(e)
                record.completed_at = datetime.now()
                db.commit()
            self._training_status[record_id]['status'] = 'failed'
            self._training_status[record_id]['error'] = str(e)
        finally:
            db.close()

    def _train_price_model(self, record_id: int, model_id: int, model_type: str, df, config: Dict, db):
        """训练价格预测模型"""
        device = config.get('device', settings.ml_device)
        predictor = PricePredictor(model_type=model_type, device=device)

        metrics = predictor.train(df, config)

        # Save model
        model_dir = f"{settings.ml_model_dir}/model_{model_id}"
        predictor.save_model(model_dir)

        # Update record
        record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
        record.status = "completed"
        record.completed_at = datetime.now()
        record.train_metrics = json.dumps({
            'loss': metrics['train_loss'],
            'val_loss': metrics['val_loss'],
            'epochs': metrics['epochs'],
        }, ensure_ascii=False)
        record.test_metrics = json.dumps({
            'best_val_accuracy': metrics['best_val_accuracy'],
            'best_val_loss': metrics['best_val_loss'],
        }, ensure_ascii=False)

        # Update model
        ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()
        ml_model.file_path = model_dir
        ml_model.features = json.dumps(predictor.feature_engineer.feature_names)
        ml_model.metrics = json.dumps({
            'accuracy': metrics['best_val_accuracy'],
            'epochs': metrics['epochs'],
        })
        ml_model.status = "active"

        db.commit()

        self._training_status[record_id]['status'] = 'completed'
        self._training_status[record_id]['progress'] = 100

    def _train_rl_agent(self, record_id: int, model_id: int, df, config: Dict, db):
        """训练强化学习代理"""
        # Build features first
        fe = FeatureEngineer()
        df = fe.build_features(df)

        # Create environment
        env = TradingEnvironment(
            df,
            initial_capital=config.get('initial_capital', 100000),
            commission=config.get('commission', 0.0003),
        )

        # Create agent
        agent = DQNAgent(
            state_size=env.state_size,
            action_size=3,
            learning_rate=config.get('learning_rate', 0.001),
        )

        # Train
        trainer = TradingTrainer(env, agent)
        metrics = trainer.train(
            num_episodes=config.get('epochs', 500),
            batch_size=config.get('batch_size', 64),
        )

        # Save agent
        model_dir = f"{settings.ml_model_dir}/model_{model_id}"
        agent.save(model_dir)

        # Update record
        record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
        record.status = "completed"
        record.completed_at = datetime.now()
        record.train_metrics = json.dumps({
            'episode_rewards': metrics['episode_rewards'][-100:],  # Last 100 episodes
            'total_episodes': metrics['total_episodes'],
        }, ensure_ascii=False)
        record.test_metrics = json.dumps({
            'best_return': metrics['best_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'final_return': metrics['final_return'],
        }, ensure_ascii=False)

        # Update model
        ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()
        ml_model.file_path = model_dir
        ml_model.metrics = json.dumps({
            'best_return': metrics['best_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
        })
        ml_model.status = "active"

        db.commit()

        self._training_status[record_id]['status'] = 'completed'
        self._training_status[record_id]['progress'] = 100

    def _train_ppo_agent(self, record_id: int, model_id: int, df, config: Dict, db):
        """训练 PPO 强化学习代理"""
        # Build features first
        fe = FeatureEngineer()
        df = fe.build_features(df)

        # Create environment
        env = TradingEnvironment(
            df,
            initial_capital=config.get('initial_capital', 100000),
            commission=config.get('commission', 0.0003),
        )

        # Create PPO agent
        agent = PPOAgent(
            state_size=env.state_size,
            learning_rate=config.get('learning_rate', 3e-4),
            gamma=config.get('gamma', 0.99),
            gae_lambda=config.get('gae_lambda', 0.95),
            clip_epsilon=config.get('clip_epsilon', 0.2),
            entropy_coef=config.get('entropy_coef', 0.01),
            ppo_epochs=config.get('ppo_epochs', 10),
        )

        # Train
        trainer = PPOTrainer(env, agent)
        metrics = trainer.train(
            num_episodes=config.get('epochs', 500),
        )

        # Save agent
        model_dir = f"{settings.ml_model_dir}/model_{model_id}"
        agent.save(model_dir)

        # Update record
        record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
        record.status = "completed"
        record.completed_at = datetime.now()
        record.train_metrics = json.dumps({
            'episode_rewards': metrics['episode_rewards'][-100:],
            'total_episodes': metrics['total_episodes'],
            'training_metrics': metrics.get('training_metrics', [])[-10:],
        }, ensure_ascii=False)
        record.test_metrics = json.dumps({
            'best_return': metrics['best_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'final_return': metrics['final_return'],
        }, ensure_ascii=False)

        # Update model
        ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()
        ml_model.file_path = model_dir
        ml_model.metrics = json.dumps({
            'best_return': metrics['best_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
        })
        ml_model.status = "active"

        db.commit()

        # 更新监控
        self.model_monitor.update_train_time(model_id)

        self._training_status[record_id]['status'] = 'completed'
        self._training_status[record_id]['progress'] = 100

    def get_training_status(self, db: Session, record_id: int) -> Dict:
        """获取训练状态"""
        record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
        if not record:
            return {'status': 'not_found'}

        # Merge DB status with in-memory status
        result = {
            'id': record.id,
            'model_id': record.model_id,
            'status': record.status,
            'started_at': str(record.started_at) if record.started_at else None,
            'completed_at': str(record.completed_at) if record.completed_at else None,
            'error_message': record.error_message,
        }

        # Add real-time progress from memory
        if record_id in self._training_status:
            mem_status = self._training_status[record_id]
            result['progress'] = mem_status.get('progress', 0)
            result['current_epoch'] = mem_status.get('current_epoch', 0)
            result['total_epochs'] = mem_status.get('total_epochs', 0)

        return result

    def get_training_metrics(self, db: Session, record_id: int) -> Dict:
        """获取训练指标"""
        record = db.query(TrainingRecord).filter(TrainingRecord.id == record_id).first()
        if not record:
            return {}

        result = {
            'id': record.id,
            'model_id': record.model_id,
            'status': record.status,
            'dataset_info': json.loads(record.dataset_info) if record.dataset_info else None,
            'train_metrics': json.loads(record.train_metrics) if record.train_metrics else None,
            'test_metrics': json.loads(record.test_metrics) if record.test_metrics else None,
        }

        return result

    # ========== 预测 ==========

    def predict(self, db: Session, model_id: int, df, symbol: str,
                market: str = "a_stock") -> Dict:
        """运行预测"""
        model = self.get_model(db, model_id)
        if not model:
            raise ValueError(f"模型 ID {model_id} 不存在")

        if model.model_type not in ('lstm', 'transformer'):
            raise ValueError(f"模型类型 {model.model_type} 不支持预测")

        device = settings.ml_device
        predictor = PricePredictor(model_type=model.model_type, device=device)

        # Load model
        if model.file_path:
            predictor.load_model(model.file_path)
        else:
            raise ValueError("模型文件不存在，请先训练模型")

        # Run prediction
        result = predictor.predict(df, seq_length=settings.ml_sequence_length)

        # Save prediction record
        prediction = PredictionRecord(
            model_id=model_id,
            symbol=symbol,
            market=market,
            prediction_date=datetime.now(),
            predicted_return=result['predicted_return'],
            predicted_direction=result['direction'],
            confidence=result['confidence'],
            features_snapshot=json.dumps({
                'probabilities': result['probabilities'],
            }),
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        result['prediction_id'] = prediction.id
        return result

    def get_predictions(self, db: Session, model_id: Optional[int] = None,
                        symbol: Optional[str] = None,
                        limit: int = 50) -> List[PredictionRecord]:
        """获取预测历史"""
        query = db.query(PredictionRecord)
        if model_id:
            query = query.filter(PredictionRecord.model_id == model_id)
        if symbol:
            query = query.filter(PredictionRecord.symbol == symbol)
        return query.order_by(PredictionRecord.created_at.desc()).limit(limit).all()

    def get_prediction_accuracy(self, db: Session, model_id: Optional[int] = None) -> Dict:
        """获取预测准确率统计"""
        query = db.query(PredictionRecord).filter(
            PredictionRecord.actual_direction.isnot(None)
        )
        if model_id:
            query = query.filter(PredictionRecord.model_id == model_id)

        predictions = query.all()
        if not predictions:
            return {'total': 0, 'accuracy': 0, 'by_direction': {}}

        correct = sum(1 for p in predictions if p.predicted_direction == p.actual_direction)
        total = len(predictions)

        by_direction = {}
        for direction in ['up', 'down', 'flat']:
            dir_preds = [p for p in predictions if p.predicted_direction == direction]
            if dir_preds:
                dir_correct = sum(1 for p in dir_preds if p.predicted_direction == p.actual_direction)
                by_direction[direction] = {
                    'total': len(dir_preds),
                    'correct': dir_correct,
                    'accuracy': dir_correct / len(dir_preds),
                }

        return {
            'total': total,
            'correct': correct,
            'accuracy': correct / total if total > 0 else 0,
            'by_direction': by_direction,
        }

    # ========== 特征工程 ==========

    def get_features(self) -> Dict:
        """列出可用特征"""
        fe = FeatureEngineer()
        return {
            'features': fe.feature_names,
            'count': len(fe.feature_names),
            'categories': {
                'price_based': ['returns_1d', 'returns_5d', 'returns_10d', 'returns_20d',
                                'log_return', 'close_to_high', 'close_to_low', 'close_to_open',
                                'high_low_range', 'close_to_ma5'],
                'moving_averages': ['ma5', 'ma10', 'ma20', 'ma60',
                                    'ma5_slope', 'ma10_slope', 'ma20_slope', 'price_above_ma20'],
                'volatility': ['volatility_5d', 'volatility_20d', 'atr_14', 'atr_ratio',
                               'bollinger_upper', 'bollinger_lower', 'bollinger_width',
                               'keltner_upper', 'keltner_lower'],
                'volume': ['volume_ratio_5d', 'volume_ratio_10d', 'volume_ma5', 'volume_ma20',
                           'obv', 'obv_ma20', 'obv_slope', 'volume_price_trend'],
                'momentum': ['rsi_6', 'rsi_14', 'rsi_24', 'macd', 'macd_signal', 'macd_hist',
                             'stochastic_k', 'stochastic_d', 'cci_20', 'williams_r'],
                'trend': ['adx_14', 'plus_di', 'minus_di', 'ichimoku_tenkan',
                          'ichimoku_kijun', 'supertrend_direction'],
                'pattern': ['doji', 'hammer', 'engulfing', 'morning_star', 'evening_star'],
                'statistical': ['z_score_20d', 'skewness_20d', 'kurtosis_20d',
                                'percentile_rank_20d', 'max_drawdown_20d'],
                'cross_features': ['ma5_cross_ma20', 'macd_cross_signal', 'rsi_divergence',
                                   'volume_breakout', 'price_momentum_acceleration'],
            }
        }

    def compute_features(self, df) -> Dict:
        """计算特征"""
        fe = FeatureEngineer()
        df = fe.build_features(df)

        feature_cols = [c for c in fe.feature_names if c in df.columns]
        latest = df[feature_cols].iloc[-1].to_dict()

        # Convert numpy types to Python types
        for key, value in latest.items():
            if hasattr(value, 'item'):
                latest[key] = value.item()
            elif pd.isna(value):
                latest[key] = None

        return {
            'features': latest,
            'count': len(feature_cols),
            'total_rows': len(df),
        }


# Singleton instance
ml_service = MLService()
