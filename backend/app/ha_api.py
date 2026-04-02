"""
V1.8 高可用与灾备 API 路由
提供集群管理、数据库复制、备份恢复、系统监控、告警管理等端点
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from .database import get_db
from .ha_service import HighAvailabilityService


router = APIRouter(prefix="/api/v1/ha", tags=["高可用与灾备"])


# ========== 请求模型 ==========

class BackupRequest(BaseModel):
    """创建备份请求"""
    backup_type: str = Field("full", description="备份类型 full/incremental")


class MetricsRequest(BaseModel):
    """性能指标请求"""
    period: str = Field("1h", description="统计周期 5m/15m/1h/6h/24h")


# ========== 集群管理 ==========

@router.get("/cluster/status")
def get_cluster_status(db: Session = Depends(get_db)):
    """获取集群状态"""
    service = HighAvailabilityService(db)
    return service.get_cluster_status()


# ========== 数据库复制管理 ==========

@router.get("/database/replication")
def get_database_replication(db: Session = Depends(get_db)):
    """获取数据库复制状态"""
    service = HighAvailabilityService(db)
    return service.check_database_replication()


@router.post("/database/failover")
def trigger_failover(db: Session = Depends(get_db)):
    """执行数据库故障转移（提升从库为主库）"""
    service = HighAvailabilityService(db)
    result = service.failover_database()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "故障转移失败"))
    return result


# ========== 数据库备份管理 ==========

@router.post("/database/backup")
def create_backup(req: BackupRequest, db: Session = Depends(get_db)):
    """创建数据库备份"""
    service = HighAvailabilityService(db)
    result = service.backup_database(backup_type=req.backup_type)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "备份失败"))
    return result


@router.get("/database/backups")
def list_backups(db: Session = Depends(get_db)):
    """获取备份列表"""
    service = HighAvailabilityService(db)
    return {"backups": service.list_backups()}


@router.post("/database/restore/{backup_id}")
def restore_backup(backup_id: str, db: Session = Depends(get_db)):
    """从备份恢复数据库"""
    service = HighAvailabilityService(db)
    result = service.restore_database(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "恢复失败"))
    return result


@router.delete("/database/backup/{backup_id}")
def delete_backup(backup_id: str, db: Session = Depends(get_db)):
    """删除备份"""
    service = HighAvailabilityService(db)
    result = service.delete_backup(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "备份不存在"))
    return result


# ========== 系统监控 ==========

@router.get("/system/health")
def get_system_health(db: Session = Depends(get_db)):
    """获取系统健康状态"""
    service = HighAvailabilityService(db)
    return service.get_system_health()


@router.get("/system/metrics")
def get_performance_metrics(
    period: str = Query("1h", description="统计周期 5m/15m/1h/6h/24h"),
    db: Session = Depends(get_db),
):
    """获取性能指标"""
    service = HighAvailabilityService(db)
    return service.get_performance_metrics(period=period)


# ========== 告警管理 ==========

@router.get("/alerts/rules")
def get_alert_rules(db: Session = Depends(get_db)):
    """获取告警规则"""
    service = HighAvailabilityService(db)
    return {"rules": service.get_alert_rules()}


@router.get("/alerts/active")
def get_active_alerts(db: Session = Depends(get_db)):
    """获取活跃告警"""
    service = HighAvailabilityService(db)
    return {"alerts": service.get_active_alerts()}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """确认告警"""
    service = HighAvailabilityService(db)
    result = service.acknowledge_alert(alert_id=alert_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "确认失败"))
    return result
