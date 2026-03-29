"""
滚动训练模块
实现时间序列滚动窗口训练，避免未来函数
"""
import pandas as pd
import numpy as np
import optuna
import joblib
from typing import Dict, List, Optional, Tuple
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from .ml_strategy import MLStockPicker


class RollingTrainer:
    """滚动训练器"""
    
    def __init__(self, 
                 train_window: int = 252,  # 训练窗口大小（交易日）
                 step: int = 21,           # 滚动步长
                 model_type: str = 'gbm',
                 model_params: Optional[Dict] = None):
        """
        初始化滚动训练器
        :param train_window: 训练窗口大小
        :param step: 滚动步长，每隔多少交易日重新训练一次
        :param model_type: 模型类型
        :param model_params: 模型参数
        """
        self.train_window = train_window
        self.step = step
        self.model_type = model_type
        self.model_params = model_params if model_params else {}
        self.models: List[Dict] = []  # 存储每个时间点训练的模型
        self.metrics_history: List[Dict] = []
    
    def train_rolling(self, 
                      X: np.ndarray, 
                      y: np.ndarray, 
                      dates: np.ndarray,
                      verbose: bool = True) -> Dict:
        """
        滚动训练
        :param X: 特征矩阵，按日期升序排列
        :param y: 标签，按日期升序排列
        :param dates: 日期数组，用于分割
        :param verbose: 是否打印训练过程
        :return: 整体训练结果
        """
        n_samples = len(X)
        self.models = []
        self.metrics_history = []
        
        # 从train_window开始，每次滚动step步
        all_preds = []
        all_true = []
        
        for start_idx in range(0, n_samples - self.train_window, self.step):
            end_train_idx = start_idx + self.train_window
            if end_train_idx >= n_samples:
                break
            
            # 训练集：[start_idx, end_train_idx)
            X_train = X[start_idx:end_train_idx]
            y_train = y[start_idx:end_train_idx]
            
            # 验证集：[end_train_idx, min(end_train_idx + step, n_samples))
            end_val_idx = min(end_train_idx + self.step, n_samples)
            X_val = X[end_train_idx:end_val_idx]
            y_val = y[end_train_idx:end_val_idx]
            
            if len(np.unique(y_train)) < 2:
                # 训练集只有一类，跳过
                continue
            
            # 训练模型
            model = MLStockPicker(self.model_type, self.model_params)
            train_metrics = model.train(X_train, y_train)
            val_pred_proba = model.predict_proba(X_val)
            val_pred = model.predict(X_val)
            
            # 计算验证集指标
            val_accuracy = (val_pred == y_val).mean()
            if len(np.unique(y_val)) > 1:
                val_auc = roc_auc_score(y_val, val_pred_proba)
            else:
                val_auc = np.nan
            
            if verbose:
                print(f"Train window [{start_idx}:{end_train_idx}], "
                      f"Val [{end_train_idx}:{end_val_idx}], "
                      f"Train AUC: {train_metrics['auc']:.4f}, Val AUC: {val_auc:.4f}")
            
            # 保存
            self.models.append({
                'start_idx': start_idx,
                'end_train_idx': end_train_idx,
                'end_val_idx': end_val_idx,
                'model': model,
                'train_dates': (dates[start_idx], dates[end_train_idx-1]),
                'val_dates': (dates[end_train_idx], dates[end_val_idx-1])
            })
            
            self.metrics_history.append({
                **train_metrics,
                'val_accuracy': val_accuracy,
                'val_auc': val_auc,
                'n_train': len(X_train),
                'n_val': len(X_val)
            })
            
            # 收集预测结果
            all_preds.extend(val_pred_proba)
            all_true.extend(y_val)
        
        # 计算整体指标
        all_preds = np.array(all_preds)
        all_true = np.array(all_true)
        all_preds_class = (all_preds >= 0.5).astype(int)
        
        overall_metrics = {
            'n_windows': len(self.models),
            'overall_accuracy': (all_preds_class == all_true).mean(),
            'overall_auc': roc_auc_score(all_true, all_preds) if len(np.unique(all_true)) > 1 else np.nan,
            'avg_train_auc': np.nanmean([m['auc'] for m in self.metrics_history]),
            'avg_val_auc': np.nanmean([m['val_auc'] for m in self.metrics_history]),
        }
        
        return overall_metrics
    
    def get_latest_model(self) -> Optional[MLStockPicker]:
        """获取最新训练的模型"""
        if not self.models:
            return None
        return self.models[-1]['model']
    
    def save_all_models(self, output_dir: str):
        """保存所有模型"""
        for i, model_info in enumerate(self.models):
            path = f"{output_dir}/model_window_{i}.pkl"
            model_info['model'].save_model(path)


class OptunaOptimizer:
    """使用Optuna进行超参数优化"""
    
    def __init__(self, 
                 X_train: np.ndarray, 
                 y_train: np.ndarray,
                 model_type: str = 'gbm',
                 n_splits: int = 5,
                 random_state: int = 42):
        """
        初始化优化器
        :param X_train: 训练特征
        :param y_train: 训练标签
        :param model_type: 模型类型
        :param n_splits: 时间序列交叉验证折数
        :param random_state: 随机种子
        """
        self.X_train = X_train
        self.y_train = y_train
        self.model_type = model_type
        self.n_splits = n_splits
        self.random_state = random_state
        self.best_params = None
        self.best_score = None
        self.study = None
    
    def objective(self, trial: optuna.Trial) -> float:
        """Optuna目标函数"""
        if self.model_type == 'gbm':
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'max_depth': trial.suggest_int('max_depth', 2, 6),
                'min_samples_split': trial.suggest_int('min_samples_split', 10, 50),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 5, 20),
                'random_state': self.random_state
            }
        elif self.model_type == 'rf':
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 2, 10),
                'min_samples_split': trial.suggest_int('min_samples_split', 10, 50),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 5, 20),
                'random_state': self.random_state
            }
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        # 时间序列交叉验证
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        scores = []
        
        for train_idx, val_idx in tscv.split(self.X_train):
            X_tr, X_val = self.X_train[train_idx], self.X_train[val_idx]
            y_tr, y_val = self.y_train[train_idx], self.y_train[val_idx]
            
            if len(np.unique(y_tr)) < 2 or len(np.unique(y_val)) < 2:
                continue
            
            model = MLStockPicker(self.model_type, params)
            model.train(X_tr, y_tr)
            y_pred_proba = model.predict_proba(X_val)
            
            if len(np.unique(y_val)) > 1:
                score = roc_auc_score(y_val, y_pred_proba)
                scores.append(score)
        
        if not scores:
            return 0.5
        
        return np.mean(scores)
    
    def optimize(self, n_trials: int = 50, show_progress_bar: bool = True) -> Dict:
        """
        执行优化
        :param n_trials: 优化迭代次数
        :param show_progress_bar: 是否显示进度条
        :return: 最佳参数
        """
        self.study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        self.study.optimize(self.objective, n_trials=n_trials, show_progress_bar=show_progress_bar)
        
        self.best_params = self.study.best_params
        self.best_score = self.study.best_value
        
        print(f"最佳验证AUC: {self.best_score:.4f}")
        print(f"最佳参数: {self.best_params}")
        
        return self.best_params
    
    def train_best_model(self) -> MLStockPicker:
        """使用最佳参数训练完整模型"""
        if self.best_params is None:
            raise ValueError("You need to run optimize first")
        
        model = MLStockPicker(self.model_type, self.best_params)
        model.train(self.X_train, self.y_train)
        return model
