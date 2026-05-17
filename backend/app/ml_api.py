"""
ML API 端点 - V2.2 深度学习策略引擎

提供模型管理、训练、预测和特征工程的 REST API。
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db
from .models import MLModel, TrainingRecord, PredictionRecord
from .ml_service import ml_service
from .ml_integration_service import ml_integration_service
from .schemas import CommonResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Schemas ==========

class CreateModelRequest(BaseModel):
    name: str
    model_type: str  # lstm / transformer / dqn
    description: Optional[str] = None
    hyperparams: Optional[dict] = None


class TrainRequest(BaseModel):
    model_id: int
    model_type: str = "lstm"  # lstm / transformer / dqn
    symbol: str = "000001"
    market: str = "a_stock"
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    seq_length: int = 60
    val_split: float = 0.2
    patience: int = 10
    initial_capital: float = 100000
    commission: float = 0.0003


class PredictRequest(BaseModel):
    model_id: int
    symbol: str = "000001"
    market: str = "a_stock"
    days: int = 120


class ComputeFeaturesRequest(BaseModel):
    symbol: str = "000001"
    market: str = "a_stock"
    days: int = 120


class OnlineLearningConfigRequest(BaseModel):
    """在线学习配置请求"""
    retrain_interval_hours: float = 24.0
    min_new_samples: int = 500


class ModelMonitorCheckRequest(BaseModel):
    """模型监控检查请求"""
    model_id: int
    model_name: str = ""


class RetrainRequest(BaseModel):
    """手动重训练请求"""
    model_id: int
    model_type: str = "lstm"
    symbol: str = "000001"
    epochs: int = 100


class GPUBenchmarkRequest(BaseModel):
    """GPU 基准测试请求"""
    batch_size: int = 32
    input_features: int = 64
    num_iterations: int = 100


# ========== V2.2 ML 原型端点 Schemas ==========

class FactorMiningRequest(BaseModel):
    """因子挖掘请求"""
    population_size: int = 50
    n_generations: int = 20
    min_ic_threshold: float = 0.01


class HPORequest(BaseModel):
    """超参优化请求"""
    symbols: List[str]
    market: str = "CN"
    n_trials: int = 50
    model_type: str = "gbm"


class RollingTrainRequest(BaseModel):
    """滚动训练请求"""
    symbols: List[str]
    market: str = "CN"
    train_window: int = 252
    step: int = 21
    model_type: str = "gbm"
    n_trials: int = 50


class PredictMLRequest(BaseModel):
    """ML 选股预测请求"""
    symbols: List[str]
    market: str = "CN"
    model_path: Optional[str] = None
    top_n: int = 3
    min_prob: float = 0.5
    model_type: str = "gbm"


# ========== Helper: Generate mock OHLCV data ==========

def _generate_mock_ohlcv(symbol: str, days: int = 120):
    """生成模拟 OHLCV 数据用于演示"""
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta

    np.random.seed(hash(symbol) % 2**31)
    dates = [datetime.now() - timedelta(days=days - i) for i in range(days)]

    # Generate realistic price series
    base_price = np.random.uniform(10, 100)
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)

    data = {
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, days)),
        'low': prices * (1 - np.random.uniform(0, 0.03, days)),
        'close': prices,
        'volume': np.random.uniform(1000000, 10000000, days),
    }
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    return df


# ========== Model Management ==========

@router.get("/models", summary="列出所有 ML 模型")
async def list_models(
    model_type: Optional[str] = Query(None, description="模型类型"),
    status: Optional[str] = Query(None, description="模型状态"),
    db: Session = Depends(get_db)
):
    """列出所有 ML 模型"""
    models = ml_service.list_models(db, model_type=model_type, status=status)
    result = []
    for m in models:
        result.append({
            'id': m.id,
            'name': m.name,
            'model_type': m.model_type,
            'version': m.version,
            'status': m.status,
            'metrics': m.metrics,
            'description': m.description,
            'created_at': str(m.created_at) if m.created_at else None,
            'updated_at': str(m.updated_at) if m.updated_at else None,
        })
    return CommonResponse(data=result)


@router.get("/models/{model_id}", summary="获取模型详情")
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """获取模型详情"""
    model = ml_service.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return CommonResponse(data={
        'id': model.id,
        'name': model.name,
        'model_type': model.model_type,
        'version': model.version,
        'status': model.status,
        'file_path': model.file_path,
        'metrics': model.metrics,
        'features': model.features,
        'hyperparams': model.hyperparams,
        'description': model.description,
        'created_at': str(model.created_at) if model.created_at else None,
        'updated_at': str(model.updated_at) if model.updated_at else None,
    })


@router.post("/models", summary="注册新模型")
async def create_model(req: CreateModelRequest, db: Session = Depends(get_db)):
    """注册新模型"""
    if req.model_type not in ('lstm', 'transformer', 'dqn', 'ppo', 'xgboost'):
        raise HTTPException(status_code=400, detail=f"不支持的模型类型: {req.model_type}")

    model = ml_service.register_model(
        db,
        name=req.name,
        model_type=req.model_type,
        description=req.description,
        hyperparams=req.hyperparams,
    )
    return CommonResponse(data={'id': model.id, 'name': model.name})


@router.delete("/models/{model_id}", summary="归档模型")
async def delete_model(model_id: int, db: Session = Depends(get_db)):
    """归档模型"""
    model = ml_service.archive_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return CommonResponse(message="模型已归档")


# ========== Training ==========

@router.post("/train", summary="启动模型训练")
async def start_training(req: TrainRequest, db: Session = Depends(get_db)):
    """启动模型训练（后台线程执行）"""
    # Check model exists
    model = ml_service.get_model(db, req.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # Generate mock data for demo (in production, fetch from database)
    df = _generate_mock_ohlcv(req.symbol, days=500)

    config = {
        'epochs': req.epochs,
        'batch_size': req.batch_size,
        'learning_rate': req.learning_rate,
        'seq_length': req.seq_length,
        'val_split': req.val_split,
        'patience': req.patience,
        'initial_capital': req.initial_capital,
        'commission': req.commission,
    }

    record = ml_service.start_training(db, req.model_id, req.model_type, df, config)

    return CommonResponse(data={
        'record_id': record.id,
        'model_id': req.model_id,
        'status': 'started',
    })


@router.get("/train/{record_id}/status", summary="获取训练状态")
async def get_training_status(record_id: int, db: Session = Depends(get_db)):
    """获取训练状态"""
    status = ml_service.get_training_status(db, record_id)
    if status.get('status') == 'not_found':
        raise HTTPException(status_code=404, detail="训练记录不存在")
    return CommonResponse(data=status)


@router.get("/train/{record_id}/metrics", summary="获取训练指标")
async def get_training_metrics(record_id: int, db: Session = Depends(get_db)):
    """获取训练指标"""
    metrics = ml_service.get_training_metrics(db, record_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="训练记录不存在")
    return CommonResponse(data=metrics)


# ========== Prediction ==========

@router.post("/predict", summary="运行预测")
async def predict(req: PredictRequest, db: Session = Depends(get_db)):
    """运行预测"""
    # Generate mock data
    df = _generate_mock_ohlcv(req.symbol, days=req.days)

    try:
        result = ml_service.predict(db, req.model_id, df, req.symbol, req.market)
        return CommonResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/predictions", summary="获取预测历史")
async def get_predictions(
    model_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取预测历史"""
    predictions = ml_service.get_predictions(db, model_id=model_id, symbol=symbol, limit=limit)
    result = []
    for p in predictions:
        result.append({
            'id': p.id,
            'model_id': p.model_id,
            'symbol': p.symbol,
            'market': p.market,
            'prediction_date': str(p.prediction_date) if p.prediction_date else None,
            'predicted_return': p.predicted_return,
            'predicted_direction': p.predicted_direction,
            'confidence': p.confidence,
            'actual_return': p.actual_return,
            'actual_direction': p.actual_direction,
            'created_at': str(p.created_at) if p.created_at else None,
        })
    return CommonResponse(data=result)


@router.get("/predictions/accuracy", summary="获取预测准确率统计")
async def get_prediction_accuracy(
    model_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """获取预测准确率统计"""
    accuracy = ml_service.get_prediction_accuracy(db, model_id=model_id)
    return CommonResponse(data=accuracy)


# ========== Features ==========

@router.get("/features", summary="列出可用特征")
async def get_features():
    """列出所有可用特征"""
    features = ml_service.get_features()
    return CommonResponse(data=features)


@router.post("/features/compute", summary="计算特征")
async def compute_features(req: ComputeFeaturesRequest):
    """计算指定股票的特征"""
    df = _generate_mock_ohlcv(req.symbol, days=req.days)
    result = ml_service.compute_features(df)
    return CommonResponse(data=result)


# ========== 在线学习 ==========

@router.post("/online-learning/start", summary="启动在线学习")
async def start_online_learning(req: OnlineLearningConfigRequest):
    """启动在线学习引擎"""
    ml_service.online_learning.start(
        retrain_interval_hours=req.retrain_interval_hours,
        min_new_samples=req.min_new_samples,
    )
    return CommonResponse(message="在线学习引擎已启动")


@router.post("/online-learning/stop", summary="停止在线学习")
async def stop_online_learning():
    """停止在线学习引擎"""
    ml_service.online_learning.stop()
    return CommonResponse(message="在线学习引擎已停止")


@router.get("/online-learning/status", summary="获取在线学习状态")
async def get_online_learning_status():
    """获取在线学习引擎状态"""
    status = ml_service.online_learning.get_status()
    return CommonResponse(data=status)


@router.get("/online-learning/drift-history", summary="获取概念漂移历史")
async def get_drift_history():
    """获取概念漂移检测历史"""
    history = ml_service.online_learning.get_drift_history()
    return CommonResponse(data=history)


@router.get("/online-learning/training-history", summary="获取在线训练历史")
async def get_online_training_history(
    limit: int = Query(20, ge=1, le=100),
):
    """获取在线学习训练历史"""
    history = ml_service.online_learning.get_training_history(limit=limit)
    return CommonResponse(data=history)


@router.get("/online-learning/versions", summary="获取模型版本列表")
async def get_model_versions(
    model_id: Optional[int] = Query(None),
):
    """获取模型版本列表"""
    versions = ml_service.online_learning.get_versions(model_id=model_id)
    return CommonResponse(data=versions)


@router.post("/online-learning/rollback", summary="回滚模型版本")
async def rollback_model_version(
    model_id: int = Query(..., description="模型 ID"),
    version: Optional[str] = Query(None, description="目标版本号（不指定则回滚到上一版本）"),
    db: Session = Depends(get_db),
):
    """回滚模型到指定版本"""
    model = ml_service.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    if not model.file_path:
        raise HTTPException(status_code=400, detail="模型文件不存在")

    success = ml_service.online_learning.rollback_model(
        model_id=model_id,
        model_dir=model.file_path,
        version=version,
    )
    if success:
        return CommonResponse(message="模型回滚成功")
    else:
        raise HTTPException(status_code=500, detail="模型回滚失败")


# ========== 模型监控 ==========

@router.get("/monitor/summary", summary="获取监控摘要")
async def get_monitor_summary():
    """获取模型监控摘要"""
    summary = ml_service.model_monitor.get_monitoring_summary()
    return CommonResponse(data=summary)


@router.post("/monitor/check", summary="运行模型检查")
async def run_model_check(req: ModelMonitorCheckRequest):
    """对指定模型运行所有监控检查"""
    result = ml_service.model_monitor.run_all_checks(
        model_id=req.model_id,
        model_name=req.model_name,
    )
    return CommonResponse(data=result)


@router.get("/monitor/alerts", summary="获取告警历史")
async def get_monitor_alerts(
    model_id: Optional[int] = Query(None, description="模型 ID"),
    alert_type: Optional[str] = Query(None, description="告警类型"),
    resolved: Optional[bool] = Query(None, description="是否已解决"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取模型监控告警历史"""
    alerts = ml_service.model_monitor.get_alerts(
        model_id=model_id,
        alert_type=alert_type,
        resolved=resolved,
        limit=limit,
    )
    return CommonResponse(data=alerts)


@router.post("/monitor/alerts/{alert_id}/resolve", summary="解决告警")
async def resolve_alert(alert_id: str):
    """解决指定告警"""
    success = ml_service.model_monitor.resolve_alert(alert_id)
    if success:
        return CommonResponse(message="告警已解决")
    else:
        raise HTTPException(status_code=404, detail="告警不存在")


@router.get("/monitor/report/{period}", summary="生成监控报告")
async def generate_monitor_report(
    period: str = "daily",  # daily / weekly
):
    """生成监控报告（日报/周报）"""
    if period not in ('daily', 'weekly'):
        raise HTTPException(status_code=400, detail="报告周期必须是 daily 或 weekly")
    report = ml_service.model_monitor.generate_report(period=period)
    return CommonResponse(data=report)


@router.post("/monitor/retrain", summary="手动触发重训练")
async def manual_retrain(req: RetrainRequest, db: Session = Depends(get_db)):
    """手动触发模型重训练"""
    model = ml_service.get_model(db, req.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    df = _generate_mock_ohlcv(req.symbol, days=500)

    config = {
        'epochs': req.epochs,
        'batch_size': 32,
        'learning_rate': 0.001,
        'seq_length': 60,
        'val_split': 0.2,
        'patience': 10,
        'initial_capital': 100000,
        'commission': 0.0003,
    }

    record = ml_service.start_training(db, req.model_id, req.model_type, df, config)

    return CommonResponse(data={
        'record_id': record.id,
        'model_id': req.model_id,
        'status': 'started',
        'message': '重训练已启动',
    })


# ========== GPU ==========

@router.get("/gpu/status", summary="获取 GPU 状态")
async def get_gpu_status():
    """获取 GPU 设备状态和资源信息"""
    from .gpu_trainer import gpu_manager
    status = gpu_manager.get_status()
    return CommonResponse(data=status)


@router.get("/gpu/info", summary="获取 GPU 详细信息")
async def get_gpu_info():
    """获取 GPU 设备详细信息"""
    from .gpu_trainer import gpu_manager
    info = gpu_manager.get_gpu_info()
    return CommonResponse(data=info)


@router.get("/gpu/memory", summary="获取显存使用情况")
async def get_gpu_memory():
    """获取 GPU 显存使用摘要"""
    from .gpu_trainer import gpu_manager
    summary = gpu_manager.get_memory_summary()
    return CommonResponse(data=summary)


@router.post("/gpu/benchmark", summary="运行 GPU 基准测试")
async def run_gpu_benchmark(req: GPUBenchmarkRequest):
    """运行 GPU 训练速度基准测试"""
    from .gpu_trainer import gpu_manager
    result = gpu_manager.run_benchmark(
        input_size=(req.batch_size, req.input_features),
        num_iterations=req.num_iterations,
    )
    return CommonResponse(data=result)


@router.post("/gpu/cache/clear", summary="清理 GPU 缓存")
async def clear_gpu_cache():
    """清理 GPU 缓存"""
    from .gpu_trainer import gpu_manager
    gpu_manager.clear_cache()
    return CommonResponse(message="GPU 缓存已清理")


# ========== V2.2 ML 原型端点 ==========

@router.post("/run_factor_mining", summary="启动 RD-Agent 自动化因子挖掘")
async def run_factor_mining(req: FactorMiningRequest):
    """启动 RD-Agent 自动化因子挖掘"""
    task_id = ml_integration_service.run_factor_mining(req.model_dump())
    return CommonResponse(data={"task_id": task_id, "status": "running"})


@router.post("/run_hpo", summary="启动 Optuna 超参优化")
async def run_hpo(req: HPORequest):
    """启动 Optuna 超参优化"""
    task_id = ml_integration_service.run_hpo(
        symbols=req.symbols,
        market=req.market,
        n_trials=req.n_trials,
        model_type=req.model_type,
    )
    return CommonResponse(data={"task_id": task_id, "status": "running"})


@router.post("/run_rolling_train", summary="启动滚动训练")
async def run_rolling_train(req: RollingTrainRequest):
    """启动滚动训练"""
    task_id = ml_integration_service.run_rolling_train(
        symbols=req.symbols,
        market=req.market,
        train_window=req.train_window,
        step=req.step,
        model_type=req.model_type,
        n_trials=req.n_trials,
    )
    return CommonResponse(data={"task_id": task_id, "status": "running"})


@router.post("/predict_ml", summary="ML 选股预测")
async def run_predict_ml(req: PredictMLRequest):
    """ML 选股预测"""
    result = ml_integration_service.run_predict(
        symbols=req.symbols,
        market=req.market,
        model_path=req.model_path,
        top_n=req.top_n,
        min_prob=req.min_prob,
        model_type=req.model_type,
    )
    return CommonResponse(data=result)


@router.get("/task_status/{task_id}", summary="查询异步任务状态")
async def get_task_status(task_id: str):
    """查询异步任务状态"""
    status = ml_integration_service.get_task_status(task_id)
    return CommonResponse(data=status)


@router.get("/data_source_status", summary="检测数据源状态")
async def get_data_source_status():
    """检测数据源状态"""
    status = ml_integration_service.check_data_source()
    return CommonResponse(data=status)
