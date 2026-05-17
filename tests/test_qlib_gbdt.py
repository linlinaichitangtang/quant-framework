"""
QlibGBDTWrapper 单元测试
验证 train → predict → predict_proba 全流程
"""

import numpy as np
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ml_strategy.qlib_gbdt import QlibGBDTWrapper


def make_classification_data(n_samples=1000, n_features=20, random_state=42):
    """生成随机二分类数据"""
    rng = np.random.RandomState(random_state)
    X = rng.randn(n_samples, n_features)
    # 用前3个特征决定标签，加入噪声
    logit = 2 * X[:, 0] - 1.5 * X[:, 1] + 0.8 * X[:, 2] + 0.5 * rng.randn(n_samples)
    y = (logit > 0).astype(int)
    return X, y


def test_basic_train_predict():
    """测试基本的训练和预测流程"""
    print("测试1: 基本 train → predict → predict_proba ...")
    X, y = make_classification_data()

    model = QlibGBDTWrapper(n_estimators=50, learning_rate=0.1, max_depth=3)
    model.fit(X, y)

    # predict
    labels = model.predict(X)
    assert labels.shape == (len(X),), f"predict shape mismatch: {labels.shape}"
    assert set(np.unique(labels)).issubset({0, 1}), f"predict labels not 0/1: {np.unique(labels)}"

    # predict_proba
    proba = model.predict_proba(X)
    assert proba.shape == (len(X), 2), f"predict_proba shape mismatch: {proba.shape}"
    assert np.allclose(proba.sum(axis=1), 1.0), "predict_proba rows don't sum to 1"
    assert np.all(proba >= 0) and np.all(proba <= 1), "probabilities out of [0,1]"

    # 一致性检查：labels 和 proba 应该一致
    proba_labels = (proba[:, 1] >= 0.5).astype(int)
    assert np.array_equal(labels, proba_labels), "predict and predict_proba inconsistent"

    # 训练准确率应该合理
    acc = np.mean(labels == y)
    print(f"  训练准确率: {acc:.4f}")
    assert acc > 0.6, f"Training accuracy too low: {acc}"
    print("  ✓ 通过")


def test_feature_importance():
    """测试特征重要性"""
    print("测试2: feature_importances_ 属性 ...")
    X, y = make_classification_data()
    model = QlibGBDTWrapper(n_estimators=50)
    model.fit(X, y)

    imp = model.feature_importances_
    assert imp.shape == (X.shape[1],), f"importance shape mismatch: {imp.shape}"
    assert np.all(imp >= 0), "negative feature importance"
    # 前3个特征重要性应该最高
    top3 = np.argsort(imp)[-3:]
    assert 0 in top3, f"Feature 0 not in top3 importances"
    print(f"  前3重要特征: {sorted(top3)}")
    print("  ✓ 通过")


def test_save_load():
    """测试模型持久化"""
    print("测试3: save_model → load_model ...")
    X, y = make_classification_data()

    model = QlibGBDTWrapper(n_estimators=50, learning_rate=0.05, max_depth=4)
    model.fit(X, y)
    original_proba = model.predict_proba(X)

    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
        path = f.name

    try:
        model.save_model(path)
        assert os.path.exists(path), "Model file not created"

        loaded = QlibGBDTWrapper()
        loaded.load_model(path)
        loaded_proba = loaded.predict_proba(X)

        assert np.allclose(original_proba, loaded_proba), "Loaded model predictions differ"
        print("  ✓ 通过")
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_train_alias():
    """测试 train() 方法（MLStockPicker 风格别名）"""
    print("测试4: train() 别名兼容 ...")
    X, y = make_classification_data()

    model = QlibGBDTWrapper(n_estimators=30)
    result = model.train(X, y)

    # train 应该返回 self（或至少可链式调用）
    assert hasattr(model, 'trained'), "train() didn't set trained flag"
    assert model.trained, "trained flag not True"

    labels = model.predict(X)
    assert labels.shape == (len(X),)
    print("  ✓ 通过")


def test_from_qlib_params():
    """测试从 qlib 风格参数创建"""
    print("测试5: from_qlib_params 工厂方法 ...")
    qlib_params = {
        'num_boost_round': 80,
        'learning_rate': 0.05,
        'max_depth': 5,
        'num_leaves': 31,
        'seed': 123,
    }
    model = QlibGBDTWrapper.from_qlib_params(qlib_params)

    assert model.n_estimators == 80
    assert model.learning_rate == 0.05
    assert model.max_depth == 5
    assert model.num_leaves == 31
    assert model.random_state == 123
    print("  ✓ 通过")


def test_ml_stock_picker_compatibility():
    """测试与 MLStockPicker 的接口兼容性"""
    print("测试6: MLStockPicker 接口兼容性 ...")
    X, y = make_classification_data(n_samples=500)

    # 模拟 MLStockPicker 的使用方式
    model = QlibGBDTWrapper(n_estimators=50)
    model.fit(X, y)

    # MLStockPicker.train() 内部调用 self.model.fit(X, y)
    # 然后 self.model.predict(X) 和 self.model.predict_proba(X)
    pred = model.predict(X)
    proba = model.predict_proba(X)

    assert pred.dtype in (np.int32, np.int64, int), f"predict dtype: {pred.dtype}"
    assert proba.ndim == 2, f"predict_proba should be 2D, got {proba.ndim}D"
    assert proba.shape[1] == 2, f"predict_proba should have 2 columns, got {proba.shape[1]}"

    # MLStockPicker.get_feature_importance() 使用 hasattr(model, 'feature_importances_')
    assert hasattr(model, 'feature_importances_')
    imp = model.feature_importances_
    assert len(imp) == X.shape[1]

    print("  ✓ 通过")


def test_small_data():
    """测试小数据集（符合项目实际数据规模）"""
    print("测试7: 小数据集 (几十条数据) ...")
    X, y = make_classification_data(n_samples=50, n_features=10)
    model = QlibGBDTWrapper(n_estimators=20, max_depth=2, num_leaves=3)
    model.fit(X, y)
    pred = model.predict(X)
    assert len(pred) == 50
    print("  ✓ 通过")


if __name__ == '__main__':
    print("=" * 60)
    print("QlibGBDTWrapper 单元测试")
    print("=" * 60)

    tests = [
        test_basic_train_predict,
        test_feature_importance,
        test_save_load,
        test_train_alias,
        test_from_qlib_params,
        test_ml_stock_picker_compatibility,
        test_small_data,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

    print("=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
