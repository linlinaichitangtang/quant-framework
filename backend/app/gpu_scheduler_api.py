"""
GPU 云计算调度 API 端点

提供训练任务提交、状态查询和 GPU 资源管理接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from .gpu_scheduler import gpu_scheduler, TaskPriority, TaskStatus
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/ml/gpu-scheduler", tags=["gpu_scheduler"])


class TaskSubmitRequest(BaseModel):
    """提交任务请求"""
    task_type: str = Field(..., description="任务类型: train_model/backtest/factor_analysis")
    params: Dict[str, Any] = Field(..., description="任务参数")
    priority: str = Field("NORMAL", description="优先级: LOW/NORMAL/HIGH/URGENT")
    required_memory_mb: int = Field(1000, ge=100, description="所需显存 MB")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    task_type: str
    status: str
    priority: str
    progress: float
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    message: str
    queue_status: Dict[str, int]


class GPUStatusResponse(BaseModel):
    """GPU 状态响应"""
    gpu_id: str
    name: str
    total_memory_mb: int
    used_memory_mb: int
    utilization: float
    in_use: bool
    current_task: Optional[str]


@router.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(
    request: TaskSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    提交训练任务

    任务会进入队列等待 GPU 资源。
    """
    try:
        priority = TaskPriority[request.priority.upper()]
    except KeyError:
        priority = TaskPriority.NORMAL

    # 添加内存需求到参数
    request.params["required_memory_mb"] = request.required_memory_mb

    # 提交任务
    task_id = gpu_scheduler.submit_task(
        task_type=request.task_type,
        params=request.params,
        priority=priority,
        user_id=current_user.get("username")
    )

    return TaskSubmitResponse(
        task_id=task_id,
        message="任务已提交",
        queue_status=gpu_scheduler.get_queue_status()
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取任务状态
    """
    status = gpu_scheduler.get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return TaskStatusResponse(**status)


@router.get("/tasks", response_model=List[TaskStatusResponse])
def list_tasks(
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    列出任务

    可按状态过滤。
    """
    # 注意：简化实现，实际应从数据库查询
    queue_status = gpu_scheduler.get_queue_status()
    tasks = []

    # 返回队列状态信息
    tasks.append(TaskStatusResponse(
        task_id="queue_info",
        task_type="info",
        status="info",
        priority="NORMAL",
        progress=0,
        created_at=datetime.now().isoformat(),
        duration_seconds=None
    ))

    return tasks


@router.delete("/tasks/{task_id}")
def cancel_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """取消任务"""
    success = gpu_scheduler.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或无法取消")

    return {"message": f"任务 {task_id} 已取消"}


@router.get("/gpus", response_model=List[GPUStatusResponse])
def list_gpus(current_user: dict = Depends(get_current_user)):
    """
    获取 GPU 列表
    """
    gpus = gpu_scheduler.get_gpu_status()
    return [GPUStatusResponse(**gpu) for gpu in gpus]


@router.get("/queue", response_model=Dict)
def get_queue_status(current_user: dict = Depends(get_current_user)):
    """
    获取队列状态
    """
    return gpu_scheduler.get_queue_status()


@router.post("/gpus/{gpu_id}/add")
def add_gpu(
    gpu_id: str,
    memory_mb: int = Field(..., ge=1000, description="显存大小 MB"),
    name: str = Field("GPU", description="GPU 名称"),
    current_user: dict = Depends(get_current_user)
):
    """添加 GPU 资源"""
    gpu_scheduler.add_gpu(gpu_id, memory_mb, name)
    return {"message": f"GPU {gpu_id} 已添加"}


@router.delete("/gpus/{gpu_id}")
def remove_gpu(
    gpu_id: str,
    current_user: dict = Depends(get_current_user)
):
    """移除 GPU 资源"""
    gpu_scheduler.remove_gpu(gpu_id)
    return {"message": f"GPU {gpu_id} 已移除"}


@router.post("/start")
def start_scheduler(current_user: dict = Depends(get_current_user)):
    """启动调度器"""
    # 调度器已在后台启动
    return {"message": "调度器运行中"}


@router.post("/stop")
def stop_scheduler(current_user: dict = Depends(get_current_user)):
    """停止调度器"""
    # 简化：调度器不能停止
    return {"message": "调度器不能停止，运行中的任务会继续执行"}