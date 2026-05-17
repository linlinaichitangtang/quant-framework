"""
模型性能监控 - V2.2 深度学习策略引擎

包含:
- ModelMonitor: 模型性能监控
- 预测准确率实时跟踪
- 准确率衰减检测（滑动窗口准确率低于阈值时触发告警）
- 模型 staleness 检测（模型最后训练时间过久）
- 数据漂移监控（输入特征分布变化检测，KS 检验）
- 告警通知（通过 notifications.py 发送告警）
- 监控报告生成（日报/周报摘要）
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertRecord:
    """告警记录"""
    alert_id: str
    model_id: int
    model_name: str
    alert_type: str  # accuracy_decay / staleness / data_drift
    severity: str  # warning / critical
    message: str
    detail: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved: bool = False


class DataDriftDetector:
    """数据漂移检测器

    使用 KS 检验（Kolmogorov-Smirnov test）检测输入特征分布变化。
    """

    def __init__(self, significance_level: float = 0.05):
        """
        Args:
            significance_level: KS 检验显著性水平
        """
        self.significance_level = significance_level
        self.reference_data: Dict[str, np.ndarray] = {}  # 特征名 -> 参考分布数据
        self.drift_history: List[Dict] = []

    def set_reference(self, feature_data: Dict[str, np.ndarray]):
        """设置参考分布

        Args:
            feature_data: {特征名: 特征值数组}
        """
        self.reference_data = {
            name: np.array(values).flatten()
            for name, values in feature_data.items()
            if len(values) > 0 and not np.all(np.isnan(values))
        }
        logger.info(f"参考分布已设置, 特征数: {len(self.reference_data)}")

    def detect_drift(self, feature_data: Dict[str, np.ndarray]) -> Dict:
        """检测数据漂移

        Args:
            feature_data: {特征名: 特征值数组}

        Returns:
            {
                'drift_detected': bool,
                'drifted_features': List[str],
                'feature_stats': Dict,
            }
        """
        if not self.reference_data:
            return {
                'drift_detected': False,
                'drifted_features': [],
                'feature_stats': {},
            }

        drifted_features = []
        feature_stats = {}

        for name, current_values in feature_data.items():
            if name not in self.reference_data:
                continue

            ref = self.reference_data[name]
            current = np.array(current_values).flatten()

            # 过滤 NaN
            ref = ref[~np.isnan(ref)]
            current = current[~np.isnan(current)]

            if len(ref) < 10 or len(current) < 10:
                continue

            # KS 检验
            try:
                ks_stat, p_value = stats.ks_2samp(ref, current)
                is_drifted = p_value < self.significance_level

                feature_stats[name] = {
                    'ks_statistic': float(ks_stat),
                    'p_value': float(p_value),
                    'is_drifted': is_drifted,
                    'ref_mean': float(np.mean(ref)),
                    'current_mean': float(np.mean(current)),
                    'ref_std': float(np.std(ref)),
                    'current_std': float(np.std(current)),
                }

                if is_drifted:
                    drifted_features.append(name)

            except Exception as e:
                logger.warning(f"特征 {name} KS 检验失败: {e}")
                continue

        drift_detected = len(drifted_features) > 0

        if drift_detected:
            drift_event = {
                'detected_at': datetime.now().isoformat(),
                'drifted_features': drifted_features,
                'feature_stats': {k: v for k, v in feature_stats.items() if v.get('is_drifted')},
            }
            self.drift_history.append(drift_event)
            logger.warning(f"数据漂移检测: {len(drifted_features)} 个特征分布发生变化")

        return {
            'drift_detected': drift_detected,
            'drifted_features': drifted_features,
            'feature_stats': feature_stats,
        }


class ModelMonitor:
    """模型性能监控

    实时跟踪预测准确率、检测准确率衰减、模型 staleness 和数据漂移。
    """

    def __init__(
        self,
        accuracy_window_size: int = 100,
        accuracy_threshold: float = 0.45,
        staleness_threshold_hours: float = 168,  # 7 天
        drift_significance_level: float = 0.05,
    ):
        """
        Args:
            accuracy_window_size: 准确率滑动窗口大小
            accuracy_threshold: 准确率告警阈值
            staleness_threshold_hours: 模型 staleness 阈值（小时）
            drift_significance_level: 数据漂移 KS 检验显著性水平
        """
        self.accuracy_window_size = accuracy_window_size
        self.accuracy_threshold = accuracy_threshold
        self.staleness_threshold_hours = staleness_threshold_hours

        # 每个模型的监控数据
        self._model_predictions: Dict[int, deque] = {}  # model_id -> 预测记录队列
        self._model_last_train_time: Dict[int, datetime] = {}  # model_id -> 最后训练时间
        self._model_reference_features: Dict[int, Dict[str, np.ndarray]] = {}  # model_id -> 参考特征

        # 数据漂移检测器（每个模型一个）
        self._drift_detectors: Dict[int, DataDriftDetector] = {}

        # 告警历史
        self._alerts: List[AlertRecord] = []
        self._max_alerts = 1000

        # 监控报告
        self._daily_reports: List[Dict] = []

    def register_model(self, model_id: int, model_name: str,
                       last_train_time: Optional[datetime] = None):
        """注册模型到监控

        Args:
            model_id: 模型 ID
            model_name: 模型名称
            last_train_time: 最后训练时间
        """
        self._model_predictions[model_id] = deque(maxlen=self.accuracy_window_size * 3)
        self._model_last_train_time[model_id] = last_train_time or datetime.now()
        self._drift_detectors[model_id] = DataDriftDetector(
            significance_level=0.05
        )
        logger.info(f"模型已注册到监控: {model_name} (ID: {model_id})")

    def unregister_model(self, model_id: int):
        """取消注册模型"""
        self._model_predictions.pop(model_id, None)
        self._model_last_train_time.pop(model_id, None)
        self._model_reference_features.pop(model_id, None)
        self._drift_detectors.pop(model_id, None)

    def update_prediction(self, model_id: int, model_name: str,
                          predicted_direction: str, actual_direction: str,
                          confidence: float = 0.0):
        """更新预测记录

        Args:
            model_id: 模型 ID
            model_name: 模型名称
            predicted_direction: 预测方向
            actual_direction: 实际方向
            confidence: 置信度
        """
        if model_id not in self._model_predictions:
            self.register_model(model_id, model_name)

        record = {
            'predicted': predicted_direction,
            'actual': actual_direction,
            'correct': predicted_direction == actual_direction,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
        }
        self._model_predictions[model_id].append(record)

    def update_train_time(self, model_id: int):
        """更新模型最后训练时间"""
        self._model_last_train_time[model_id] = datetime.now()

    def set_reference_features(self, model_id: int, feature_data: Dict[str, np.ndarray]):
        """设置模型参考特征分布

        Args:
            model_id: 模型 ID
            feature_data: {特征名: 特征值数组}
        """
        self._model_reference_features[model_id] = feature_data
        if model_id in self._drift_detectors:
            self._drift_detectors[model_id].set_reference(feature_data)

    def check_accuracy(self, model_id: int) -> Dict:
        """检查模型预测准确率

        Args:
            model_id: 模型 ID

        Returns:
            {
                'current_accuracy': float,
                'window_accuracy': float,
                'total_predictions': int,
                'correct_predictions': int,
                'alert_triggered': bool,
            }
        """
        if model_id not in self._model_predictions:
            return {
                'current_accuracy': 0.0,
                'window_accuracy': 0.0,
                'total_predictions': 0,
                'correct_predictions': 0,
                'alert_triggered': False,
            }

        predictions = list(self._model_predictions[model_id])
        if not predictions:
            return {
                'current_accuracy': 0.0,
                'window_accuracy': 0.0,
                'total_predictions': 0,
                'correct_predictions': 0,
                'alert_triggered': False,
            }

        # 总体准确率
        total_correct = sum(1 for p in predictions if p['correct'])
        total_accuracy = total_correct / len(predictions)

        # 窗口准确率
        window = predictions[-self.accuracy_window_size:]
        window_correct = sum(1 for p in window if p['correct'])
        window_accuracy = window_correct / len(window)

        # 检查是否触发告警
        alert_triggered = False
        if len(window) >= self.accuracy_window_size // 2 and window_accuracy < self.accuracy_threshold:
            alert_triggered = True
            self._create_alert(
                model_id=model_id,
                model_name=f"Model_{model_id}",
                alert_type='accuracy_decay',
                severity='warning' if window_accuracy >= 0.35 else 'critical',
                message=f"模型准确率下降至 {window_accuracy:.4f}，低于阈值 {self.accuracy_threshold}",
                detail={
                    'window_accuracy': window_accuracy,
                    'total_accuracy': total_accuracy,
                    'window_size': len(window),
                    'threshold': self.accuracy_threshold,
                },
            )

        return {
            'current_accuracy': total_accuracy,
            'window_accuracy': window_accuracy,
            'total_predictions': len(predictions),
            'correct_predictions': total_correct,
            'alert_triggered': alert_triggered,
        }

    def check_staleness(self, model_id: int, model_name: str = "") -> Dict:
        """检查模型 staleness

        Args:
            model_id: 模型 ID
            model_name: 模型名称

        Returns:
            {
                'is_stale': bool,
                'last_train_time': str,
                'hours_since_train': float,
                'threshold_hours': float,
            }
        """
        last_train = self._model_last_train_time.get(model_id)
        if not last_train:
            return {
                'is_stale': False,
                'last_train_time': None,
                'hours_since_train': 0,
                'threshold_hours': self.staleness_threshold_hours,
            }

        hours_since = (datetime.now() - last_train).total_seconds() / 3600
        is_stale = hours_since > self.staleness_threshold_hours

        if is_stale:
            self._create_alert(
                model_id=model_id,
                model_name=model_name or f"Model_{model_id}",
                alert_type='staleness',
                severity='warning',
                message=f"模型已 {hours_since:.1f} 小时未训练，超过阈值 {self.staleness_threshold_hours} 小时",
                detail={
                    'hours_since_train': hours_since,
                    'threshold_hours': self.staleness_threshold_hours,
                    'last_train_time': last_train.isoformat(),
                },
            )

        return {
            'is_stale': is_stale,
            'last_train_time': last_train.isoformat(),
            'hours_since_train': hours_since,
            'threshold_hours': self.staleness_threshold_hours,
        }

    def check_data_drift(self, model_id: int,
                         feature_data: Optional[Dict[str, np.ndarray]] = None) -> Dict:
        """检查数据漂移

        Args:
            model_id: 模型 ID
            feature_data: 当前特征数据（可选）

        Returns:
            漂移检测结果
        """
        detector = self._drift_detectors.get(model_id)
        if not detector:
            return {
                'drift_detected': False,
                'drifted_features': [],
                'feature_stats': {},
            }

        if feature_data is None:
            feature_data = self._model_reference_features.get(model_id, {})

        if not feature_data:
            return {
                'drift_detected': False,
                'drifted_features': [],
                'feature_stats': {},
            }

        result = detector.detect_drift(feature_data)

        if result['drift_detected']:
            self._create_alert(
                model_id=model_id,
                model_name=f"Model_{model_id}",
                alert_type='data_drift',
                severity='warning',
                message=f"检测到 {len(result['drifted_features'])} 个特征分布发生变化",
                detail=result,
            )

        return result

    def run_all_checks(self, model_id: int, model_name: str = "") -> Dict:
        """运行所有检查

        Args:
            model_id: 模型 ID
            model_name: 模型名称

        Returns:
            综合检查结果
        """
        accuracy = self.check_accuracy(model_id)
        staleness = self.check_staleness(model_id, model_name)
        drift = self.check_data_drift(model_id)

        return {
            'model_id': model_id,
            'model_name': model_name,
            'checked_at': datetime.now().isoformat(),
            'accuracy': accuracy,
            'staleness': staleness,
            'data_drift': drift,
            'overall_status': 'healthy' if not (
                accuracy['alert_triggered'] or
                staleness['is_stale'] or
                drift['drift_detected']
            ) else 'warning',
        }

    def _create_alert(self, model_id: int, model_name: str,
                      alert_type: str, severity: str,
                      message: str, detail: Dict = None):
        """创建告警记录"""
        alert = AlertRecord(
            alert_id=f"{alert_type}_{model_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            model_id=model_id,
            model_name=model_name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            detail=detail or {},
        )

        # 检查是否已有相同类型的未解决告警（避免重复）
        existing = [a for a in self._alerts
                    if a.model_id == model_id and a.alert_type == alert_type and not a.resolved]
        if existing:
            # 更新已有告警
            existing[-1].message = message
            existing[-1].detail = detail or {}
            existing[-1].created_at = alert.created_at
            logger.warning(f"告警已更新: {message}")
        else:
            self._alerts.append(alert)
            logger.warning(f"新告警: {message}")

        # 限制告警数量
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        # 异步发送通知
        try:
            self._send_alert_notification(alert)
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")

    def _send_alert_notification(self, alert: AlertRecord):
        """发送告警通知"""
        try:
            from .notifications import notification_service, Notification
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._async_send_notification(alert))
            else:
                loop.run_until_complete(self._async_send_notification(alert))
        except Exception as e:
            logger.debug(f"告警通知发送跳过: {e}")

    async def _async_send_notification(self, alert: AlertRecord):
        """异步发送告警通知"""
        try:
            from .notifications import notification_service, Notification

            notification = Notification(
                title=f"[模型监控] {alert.alert_type}: {alert.model_name}",
                content=alert.message,
                channel="alert",
                level=alert.severity,
                data={
                    'alert_id': alert.alert_id,
                    'model_id': alert.model_id,
                    'model_name': alert.model_name,
                    'alert_type': alert.alert_type,
                    'detail': alert.detail,
                },
            )
            await notification_service.send(notification)
        except Exception as e:
            logger.debug(f"告警通知发送失败: {e}")

    def get_alerts(self, model_id: Optional[int] = None,
                   alert_type: Optional[str] = None,
                   resolved: Optional[bool] = None,
                   limit: int = 50) -> List[Dict]:
        """获取告警历史

        Args:
            model_id: 模型 ID 过滤
            alert_type: 告警类型过滤
            resolved: 是否已解决
            limit: 返回数量限制

        Returns:
            告警列表
        """
        alerts = self._alerts

        if model_id is not None:
            alerts = [a for a in alerts if a.model_id == model_id]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        # 返回最新的
        alerts = alerts[-limit:]

        return [
            {
                'alert_id': a.alert_id,
                'model_id': a.model_id,
                'model_name': a.model_name,
                'alert_type': a.alert_type,
                'severity': a.severity,
                'message': a.message,
                'detail': a.detail,
                'created_at': a.created_at,
                'resolved': a.resolved,
            }
            for a in alerts
        ]

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警

        Args:
            alert_id: 告警 ID

        Returns:
            是否成功
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                logger.info(f"告警已解决: {alert_id}")
                return True
        return False

    def generate_report(self, period: str = 'daily') -> Dict:
        """生成监控报告

        Args:
            period: 报告周期 (daily/weekly)

        Returns:
            监控报告字典
        """
        now = datetime.now()
        if period == 'weekly':
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(days=1)

        # 收集各模型状态
        model_summaries = []
        for model_id in self._model_predictions:
            accuracy = self.check_accuracy(model_id)
            staleness = self.check_staleness(model_id)
            model_summaries.append({
                'model_id': model_id,
                'accuracy': accuracy,
                'staleness': staleness,
            })

        # 统计告警
        period_alerts = [
            a for a in self._alerts
            if datetime.fromisoformat(a.created_at) >= start_time
        ]
        alert_summary = {
            'total': len(period_alerts),
            'by_type': {},
            'by_severity': {},
            'unresolved': len([a for a in period_alerts if not a.resolved]),
        }
        for a in period_alerts:
            alert_summary['by_type'][a.alert_type] = alert_summary['by_type'].get(a.alert_type, 0) + 1
            alert_summary['by_severity'][a.severity] = alert_summary['by_severity'].get(a.severity, 0) + 1

        report = {
            'period': period,
            'generated_at': now.isoformat(),
            'start_time': start_time.isoformat(),
            'monitored_models': len(self._model_predictions),
            'model_summaries': model_summaries,
            'alert_summary': alert_summary,
            'overall_health': 'healthy' if alert_summary['unresolved'] == 0 else 'warning',
        }

        self._daily_reports.append(report)

        return report

    def get_monitoring_summary(self) -> Dict:
        """获取监控摘要

        Returns:
            监控摘要字典
        """
        return {
            'monitored_models': list(self._model_predictions.keys()),
            'total_models': len(self._model_predictions),
            'total_alerts': len(self._alerts),
            'unresolved_alerts': len([a for a in self._alerts if not a.resolved]),
            'accuracy_threshold': self.accuracy_threshold,
            'staleness_threshold_hours': self.staleness_threshold_hours,
            'accuracy_window_size': self.accuracy_window_size,
        }
