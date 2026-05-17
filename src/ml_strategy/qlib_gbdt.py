"""
Qlib GBDT 模型封装 - sklearn 接口兼容
用 LightGBM 后端替换 MLStockPicker 内部的 sklearn GradientBoostingClassifier

实现原理：
- 底层直接调用 lightgbm（qlib 内部也用它）
- 上层暴露 sklearn 风格的 fit/predict/predict_proba 接口
- 兼容 MLStockPicker 的 model 属性使用方式
"""

import numpy as np
import pandas as pd
import joblib
import lightgbm as lgb
from typing import Dict, Optional, List


class QlibGBDTWrapper:
    """
    Qlib GBDT 模型封装

    sklearn 接口兼容，直接替换 MLStockPicker 内部的 GBM。
    底层使用 LightGBM 引擎（与 qlib.contrib.model.gbdt.LGBModel 同源）。

    使用示例：
        model = QlibGBDTWrapper(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=3,
            num_leaves=31
        )
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)
        labels = model.predict(X_test)
    """

    def __init__(self, n_estimators=100, learning_rate=0.1, max_depth=3,
                 num_leaves=31, min_child_samples=20, subsample=1.0,
                 colsample_bytree=1.0, random_state=42, **kwargs):
        """
        初始化 Qlib GBDT 封装器

        参数与 qlib.contrib.model.gbdt.LGBModel / lightgbm 对齐：
        :param n_estimators: boosting 迭代轮数 (等价于 num_boost_round)
        :param learning_rate: 学习率
        :param max_depth: 树最大深度（-1 表示不限制）
        :param num_leaves: 叶子节点数
        :param min_child_samples: 最小叶子样本数
        :param subsample: 行采样比例
        :param colsample_bytree: 列采样比例
        :param random_state: 随机种子
        :param kwargs: 传给 lightgbm 的额外参数
        """
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.num_leaves = num_leaves
        self.min_child_samples = min_child_samples
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state
        self.extra_params = kwargs

        # lightgbm 参数字典（与 qlib.LGBModel 一致的命名风格）
        self.params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'learning_rate': learning_rate,
            'max_depth': max_depth,
            'num_leaves': num_leaves,
            'min_child_samples': min_child_samples,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'seed': random_state,
            'verbose': -1,
            **kwargs,
        }

        self.model = None  # type: Optional[lgb.Booster]
        self.feature_names = None  # type: Optional[List[str]]
        self.trained = False

    def fit(self, X: np.ndarray, y: np.ndarray, **fit_params):
        """
        训练模型（sklearn 兼容接口）

        :param X: 特征矩阵 (n_samples, n_features)
        :param y: 标签 (n_samples,)，0/1 二分类
        :param fit_params: 可选的额外参数（如 eval_set, early_stopping_rounds）
        :return: self
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
            X = X.values
        else:
            n_features = X.shape[1]
            self.feature_names = [f'f{i}' for i in range(n_features)]

        y = np.asarray(y, dtype=np.float64)

        dtrain = lgb.Dataset(X, label=y, feature_name=self.feature_names, free_raw_data=False)

        early_stopping_rounds = fit_params.pop('early_stopping_rounds', None)
        callbacks = [lgb.log_evaluation(period=0)]  # 静默
        if early_stopping_rounds:
            callbacks.append(lgb.early_stopping(early_stopping_rounds))

        eval_set = fit_params.get('eval_set', None)
        valid_sets = None
        valid_names = None
        if eval_set:
            valid_sets = [lgb.Dataset(e[0], label=e[1], feature_name=self.feature_names) for e in eval_set]
            valid_names = [f'valid_{i}' for i in range(len(eval_set))]

        self.model = lgb.train(
            self.params,
            dtrain,
            num_boost_round=self.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
            **fit_params,
        )

        self.trained = True
        return self

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs):
        """
        训练模型（MLStockPicker 风格接口，等价于 fit）

        :param X: 特征矩阵
        :param y: 标签
        :return: self（兼容 sklearn 返回值）
        """
        return self.fit(X, y, **kwargs)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测类别标签（sklearn 兼容接口）

        :param X: 特征矩阵
        :return: 预测标签 (n_samples,)，值为 0 或 1
        """
        if not self.trained or self.model is None:
            raise ValueError("Model not fitted yet. Call fit() first.")

        proba = self._raw_predict(X)
        return (proba >= 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        预测类别概率（sklearn 兼容接口）

        :param X: 特征矩阵
        :return: 概率矩阵 (n_samples, 2)，列0为负类概率，列1为正类概率
        """
        if not self.trained or self.model is None:
            raise ValueError("Model not fitted yet. Call fit() first.")

        p1 = self._raw_predict(X)
        return np.column_stack([1 - p1, p1])

    def _raw_predict(self, X: np.ndarray) -> np.ndarray:
        """内部方法：获取正类概率"""
        if isinstance(X, pd.DataFrame):
            X = X.values
        X = np.asarray(X, dtype=np.float64)
        proba = self.model.predict(X)
        return np.clip(proba, 0.0, 1.0)

    @property
    def feature_importances_(self) -> np.ndarray:
        """
        特征重要性（sklearn 兼容属性）

        :return: 特征重要性数组 (n_features,)
        """
        if not self.trained or self.model is None:
            raise ValueError("Model not fitted yet.")
        return self.model.feature_importance(importance_type='gain')

    def save_model(self, path: str):
        """
        保存模型到文件

        :param path: 保存路径（.pkl 后缀推荐）
        """
        state = {
            'params': self.params,
            'n_estimators': self.n_estimators,
            'feature_names': self.feature_names,
            'trained': self.trained,
            'model': self.model,  # lgb.Booster 可被 joblib 序列化
        }
        joblib.dump(state, path)

    def load_model(self, path: str):
        """
        从文件加载模型

        :param path: 模型文件路径
        """
        state = joblib.load(path)
        self.params = state['params']
        self.n_estimators = state['n_estimators']
        self.feature_names = state['feature_names']
        self.trained = state['trained']
        self.model = state['model']

        # 同步构造函数参数
        self.learning_rate = self.params.get('learning_rate', 0.1)
        self.max_depth = self.params.get('max_depth', 3)
        self.num_leaves = self.params.get('num_leaves', 31)
        self.min_child_samples = self.params.get('min_child_samples', 20)
        self.subsample = self.params.get('subsample', 1.0)
        self.colsample_bytree = self.params.get('colsample_bytree', 1.0)
        self.random_state = self.params.get('seed', 42)

    @classmethod
    def from_qlib_params(cls, qlib_params: Dict, **kwargs) -> 'QlibGBDTWrapper':
        """
        从 qlib 风格参数创建实例

        qlib 的参数名和 lightgbm 参数名一致，直接传入即可。

        :param qlib_params: qlib/LightGBM 参数字典
        :param kwargs: 额外的构造函数参数
        """
        wrapper_params = dict(kwargs)
        # 将 lightgbm 参数映射到构造函数参数
        if 'num_boost_round' in qlib_params:
            wrapper_params['n_estimators'] = qlib_params.pop('num_boost_round')
        if 'n_estimators' in qlib_params:
            wrapper_params['n_estimators'] = qlib_params.pop('n_estimators')
        if 'learning_rate' in qlib_params:
            wrapper_params['learning_rate'] = qlib_params.pop('learning_rate')
        if 'max_depth' in qlib_params:
            wrapper_params['max_depth'] = qlib_params.pop('max_depth')
        if 'num_leaves' in qlib_params:
            wrapper_params['num_leaves'] = qlib_params.pop('num_leaves')
        if 'min_child_samples' in qlib_params:
            wrapper_params['min_child_samples'] = qlib_params.pop('min_child_samples')
        if 'subsample' in qlib_params:
            wrapper_params['subsample'] = qlib_params.pop('subsample')
        if 'colsample_bytree' in qlib_params:
            wrapper_params['colsample_bytree'] = qlib_params.pop('colsample_bytree')
        if 'seed' in qlib_params:
            wrapper_params['random_state'] = qlib_params.pop('seed')
        if 'random_state' in qlib_params:
            wrapper_params['random_state'] = qlib_params.pop('random_state')

        # 剩余参数传给 extra_params
        return cls(**wrapper_params, **qlib_params)
