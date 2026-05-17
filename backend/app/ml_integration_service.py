"""
ML Integration Service - Phase B
封装所有 ML 原型模块的调度逻辑，对外提供统一接口
"""
import os
import sys
import uuid
import logging
import threading
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

# 将 backend/src 加入 path，以便引用 ml_strategy / data / rd_agent
_src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from ml_strategy import (
    FutuDataFetcher,
    FactorExtractor,
    LabelConstructor,
    MLStockPicker,
    Backtester,
    RollingTrainer,
    OptunaOptimizer,
)
from data.qlib_adapter import QlibExpressionParser, QlibFactorEngine
from rd_agent import RDAgent, RDConfig

logger = logging.getLogger(__name__)


def _generate_mock_stock_data(symbols: List[str], days: int = 300) -> Dict[str, pd.DataFrame]:
    """生成模拟股票 OHLCV 数据，供模块在 Futu OpenD 不可用时使用"""
    result = {}
    end = datetime.now()
    dates = [end - timedelta(days=days - i) for i in range(days)]
    for sym in symbols:
        seed = hash(sym) % 2**31
        rng = np.random.RandomState(seed)
        base = rng.uniform(20, 200)
        rets = rng.normal(0.0005, 0.02, days)
        prices = base * np.cumprod(1 + rets)
        df = pd.DataFrame({
            'trade_date': [d.strftime('%Y%m%d') for d in dates],
            'open': prices * (1 + rng.uniform(-0.01, 0.01, days)),
            'high': prices * (1 + rng.uniform(0, 0.03, days)),
            'low': prices * (1 - rng.uniform(0, 0.03, days)),
            'close': prices,
            'volume': rng.uniform(1_000_000, 10_000_000, days),
            'amount': rng.uniform(5e7, 5e8, days),
        })
        df['trade_date_dt'] = pd.to_datetime(df['trade_date'])
        df = df.set_index('trade_date_dt').sort_index()
        result[sym] = df
    return result


class MLIntegrationService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._tasks: Dict[str, Dict[str, Any]] = {}
                cls._instance._executor = ThreadPoolExecutor(max_workers=4)
                cls._instance._futu_cache: Dict[str, Any] = {}
            return cls._instance

    # ------------------------------------------------------------------ #
    #  数据获取（内部工具）
    # ------------------------------------------------------------------ #
    def _fetch_data(self, symbols: List[str], market: str,
                    start_date: str = "20240101",
                    end_date: str = None) -> Dict[str, pd.DataFrame]:
        """尝试用 Futu 拉取数据，失败时 fallback 到模拟数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        try:
            fetcher = FutuDataFetcher()
            result = {}
            for sym in symbols:
                try:
                    df = fetcher.get_daily_data(sym, start_date=start_date, end_date=end_date)
                    if len(df) > 0:
                        result[sym] = df
                except Exception:
                    continue
            if result:
                return result
        except Exception:
            pass
        logger.info("Futu OpenD 不可用，使用模拟数据")
        return _generate_mock_stock_data(symbols)

    # ------------------------------------------------------------------ #
    #  B4: 数据源检测
    # ------------------------------------------------------------------ #
    def check_data_source(self) -> Dict[str, str]:
        """检测 Futu OpenD 是否可用"""
        try:
            fetcher = FutuDataFetcher()
            quote = fetcher.get_stock_quote("QQQ")
            return {"status": "ok", "source": "futu", "sample": str(quote)}
        except Exception:
            return {"status": "fallback", "source": "mock",
                    "note": "Futu OpenD 未启动，使用模拟数据"}

    # ------------------------------------------------------------------ #
    #  B1: 因子挖掘（异步）
    # ------------------------------------------------------------------ #
    def run_factor_mining(self, config: Dict[str, Any]) -> str:
        task_id = f"fm_{uuid.uuid4().hex[:8]}"
        self._tasks[task_id] = {"status": "running", "config": config}

        def _run():
            try:
                rd_config = RDConfig(
                    population_size=config.get("population_size", 50),
                    n_generations=config.get("n_generations", 20),
                    crossover_rate=0.7,
                    mutation_rate=0.2,
                    elite_ratio=0.1,
                    max_expr_depth=5,
                    min_ic_threshold=config.get("min_ic_threshold", 0.01),
                )
                # RDAgent 需要 DataFrame 数据，内部生成模拟多股票数据
                mock_data = _generate_mock_stock_data(
                    [f"STOCK_{i:03d}" for i in range(10)], days=300
                )
                rows = []
                for sym, df in mock_data.items():
                    tmp = df.copy()
                    tmp['ts_code'] = sym
                    rows.append(tmp)
                mining_data = pd.concat(rows, ignore_index=True)

                agent = RDAgent(mining_data, rd_config)
                top_factors = agent.evolve()
                results = [
                    {
                        "rank": i + 1,
                        "expression": fg.expression,
                        "ic": round(float(fg.ic or 0), 4),
                        "ir": round(float(fg.ir or 0), 4),
                        "fitness": round(float(fg.fitness or 0), 4),
                    }
                    for i, fg in enumerate(top_factors)
                ]
                self._tasks[task_id] = {"status": "done", "result": results}
            except Exception as e:
                logger.exception("factor_mining failed")
                self._tasks[task_id] = {"status": "error", "error": str(e)}

        self._executor.submit(_run)
        return task_id

    # ------------------------------------------------------------------ #
    #  B2: HPO 超参优化（异步）
    # ------------------------------------------------------------------ #
    def run_hpo(self, symbols: List[str], market: str,
                n_trials: int = 50, model_type: str = "gbm") -> str:
        task_id = f"hpo_{uuid.uuid4().hex[:8]}"
        self._tasks[task_id] = {"status": "running"}

        def _run():
            try:
                data = self._fetch_data(symbols, market)
                sym0 = list(data.keys())[0]
                df = data[sym0]

                fe = FactorExtractor()
                features_df, feature_cols = fe.extract_all_factors(df)
                lc = LabelConstructor()
                labeled_df = lc.construct_label(df)

                # 对齐特征与标签
                common_idx = features_df.index.intersection(labeled_df.index)
                X = features_df.loc[common_idx][feature_cols].values
                y = labeled_df.loc[common_idx]['y'].values

                mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
                X, y = X[mask], y[mask]

                optimizer = OptunaOptimizer(X, y, model_type=model_type)
                best = optimizer.optimize(n_trials=n_trials)

                self._tasks[task_id] = {
                    "status": "done",
                    "result": {
                        "best_params": best.get("best_params"),
                        "best_ic": round(float(best.get("best_value", 0)), 4),
                        "n_trials": n_trials,
                    },
                }
            except Exception as e:
                logger.exception("hpo failed")
                self._tasks[task_id] = {"status": "error", "error": str(e)}

        self._executor.submit(_run)
        return task_id

    # ------------------------------------------------------------------ #
    #  B3: 滚动训练（异步）
    # ------------------------------------------------------------------ #
    def run_rolling_train(self, symbols: List[str], market: str,
                          train_window: int = 252, step: int = 21,
                          model_type: str = "gbm",
                          n_trials: int = 50) -> str:
        task_id = f"rt_{uuid.uuid4().hex[:8]}"
        self._tasks[task_id] = {"status": "running"}

        def _run():
            try:
                data = self._fetch_data(symbols, market)
                sym0 = list(data.keys())[0]
                df = data[sym0]

                fe = FactorExtractor()
                features_df, feature_cols = fe.extract_all_factors(df)
                lc = LabelConstructor()
                labeled_df = lc.construct_label(df)

                common_idx = features_df.index.intersection(labeled_df.index)
                X = features_df.loc[common_idx][feature_cols].values
                y = labeled_df.loc[common_idx]['y'].values
                dates = np.array(common_idx)

                mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
                X, y, dates = X[mask], y[mask], dates[mask]

                trainer = RollingTrainer(
                    train_window=train_window, step=step, model_type=model_type
                )
                result = trainer.train_rolling(X, y, dates=dates)

                self._tasks[task_id] = {
                    "status": "done",
                    "result": {
                        "overall_accuracy": round(float(result.get("overall_accuracy", 0)), 4),
                        "overall_auc": round(float(result.get("overall_auc", 0)), 4),
                        "avg_train_auc": round(float(result.get("avg_train_auc", 0)), 4),
                        "avg_val_auc": round(float(result.get("avg_val_auc", 0)), 4),
                        "symbols": symbols,
                    },
                }
            except Exception as e:
                logger.exception("rolling_train failed")
                self._tasks[task_id] = {"status": "error", "error": str(e)}

        self._executor.submit(_run)
        return task_id

    # ------------------------------------------------------------------ #
    #  B4: ML 选股预测（同步）
    # ------------------------------------------------------------------ #
    def run_predict(self, symbols: List[str], market: str,
                    model_path: Optional[str], top_n: int = 3,
                    min_prob: float = 0.5,
                    model_type: str = "gbm") -> Dict:
        try:
            data = self._fetch_data(symbols, market,
                                    start_date=(datetime.now() - timedelta(days=120)).strftime('%Y%m%d'))

            fe = FactorExtractor()
            lc = LabelConstructor()
            all_selections = []

            for sym, df in data.items():
                try:
                    features_df, feature_cols = fe.extract_all_factors(df)
                    labeled_df = lc.construct_label(df)

                    common_idx = features_df.index.intersection(labeled_df.index)
                    X = features_df.loc[common_idx][feature_cols]
                    y = labeled_df.loc[common_idx]['y'].values

                    mask = ~(np.isnan(X.values).any(axis=1) | np.isnan(y))
                    X_clean = X.values[mask]
                    y_clean = y[mask]

                    if len(X_clean) < 20 or len(np.unique(y_clean)) < 2:
                        continue

                    picker = MLStockPicker(model_type=model_type)
                    picker.train(X_clean, y_clean, scale=False)
                    proba = picker.predict_proba(X_clean[-1:])

                    conf = float(proba[0][1])
                    if conf >= min_prob:
                        all_selections.append({
                            "symbol": sym,
                            "confidence": round(conf, 4),
                            "direction": "UP" if conf > 0.5 else "DOWN",
                        })
                except Exception:
                    continue

            all_selections.sort(key=lambda x: x["confidence"], reverse=True)
            return {"selections": all_selections[:top_n]}
        except Exception as e:
            logger.exception("predict failed")
            return {"selections": [], "error": str(e)}

    # ------------------------------------------------------------------ #
    #  异步任务状态查询
    # ------------------------------------------------------------------ #
    def get_task_status(self, task_id: str) -> Dict:
        return self._tasks.get(task_id, {"status": "not_found"})


# 单例
ml_integration_service = MLIntegrationService()
