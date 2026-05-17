"""
GPU 云计算调度

提供训练任务的队列管理、自动扩缩容和 GPU 资源调度。
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from collections import deque

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"   # 已取消


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class TrainingTask:
    """训练任务"""
    task_id: str
    task_type: str  # "train_model" / "backtest" / "factor_analysis"
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0-1
    result: Optional[Any] = None
    error: Optional[str] = None
    user_id: Optional[str] = None


class GPUResource:
    """GPU 资源"""
    def __init__(self, gpu_id: str, memory_mb: int, name: str = "Unknown"):
        self.gpu_id = gpu_id
        self.memory_mb = memory_mb
        self.name = name
        self.occupied_memory_mb = 0
        self.current_task_id: Optional[str] = None
        self.utilization = 0.0  # 0-100%


class TaskQueue:
    """任务队列（优先级队列）"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._pending: deque[TrainingTask] = deque()
        self._running: Dict[str, TrainingTask] = {}
        self._completed: Dict[str, TrainingTask] = {}
        self._lock = asyncio.Lock()

    async def add(self, task: TrainingTask) -> bool:
        """添加任务"""
        async with self._lock:
            if len(self._pending) >= self.max_size:
                return False

            # 按优先级插入
            inserted = False
            for i, t in enumerate(self._pending):
                if task.priority.value > t.priority.value:
                    self._pending.insert(i, task)
                    inserted = True
                    break

            if not inserted:
                self._pending.append(task)

            logger.info(f"任务已添加: {task.task_id}, 优先级: {task.priority.name}")
            return True

    async def get_next(self) -> Optional[TrainingTask]:
        """获取下一个待执行任务"""
        async with self._lock:
            if not self._pending:
                return None

            task = self._pending.popleft()
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running[task.task_id] = task
            return task

    async def complete(self, task_id: str, result: Any = None):
        """标记任务完成"""
        async with self._lock:
            if task_id in self._running:
                task = self._running.pop(task_id)
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                task.progress = 1.0
                self._completed[task_id] = task
                logger.info(f"任务完成: {task_id}")

    async def fail(self, task_id: str, error: str):
        """标记任务失败"""
        async with self._lock:
            if task_id in self._running:
                task = self._running.pop(task_id)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = error
                self._completed[task_id] = task
                logger.error(f"任务失败: {task_id}, error: {error}")

    async def cancel(self, task_id: str):
        """取消任务"""
        async with self._lock:
            # 从 pending 中移除
            for i, t in enumerate(self._pending):
                if t.task_id == task_id:
                    self._pending.remove(t)
                    t.status = TaskStatus.CANCELLED
                    self._completed[task_id] = t
                    return True

            # 从 running 中移除
            if task_id in self._running:
                task = self._running.pop(task_id)
                task.status = TaskStatus.CANCELLED
                self._completed[task_id] = task
                return True

        return False

    def get_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        for task in self._pending:
            if task.task_id == task_id:
                return self._format_task(task)

        if task_id in self._running:
            return self._format_task(self._running[task_id])

        if task_id in self._completed:
            return self._format_task(self._completed[task_id])

        return None

    def _format_task(self, task: TrainingTask) -> Dict:
        """格式化任务信息"""
        duration = None
        if task.started_at:
            end = task.completed_at or datetime.now()
            duration = (end - task.started_at).total_seconds()

        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "priority": task.priority.name,
            "progress": task.progress,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "duration_seconds": duration,
            "error": task.error
        }

    def get_pending_count(self) -> int:
        return len(self._pending)

    def get_running_count(self) -> int:
        return len(self._running)


class GPUScheduler:
    """
    GPU 任务调度器

    管理 GPU 资源分配和任务调度。
    """

    def __init__(self):
        self._resources: Dict[str, GPUResource] = {}
        self._queue = TaskQueue()
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._running = False

    def add_gpu(self, gpu_id: str, memory_mb: int, name: str = "GPU"):
        """添加 GPU 资源"""
        self._resources[gpu_id] = GPUResource(gpu_id, memory_mb, name)
        logger.info(f"已添加 GPU: {gpu_id}, 内存: {memory_mb}MB")

    def remove_gpu(self, gpu_id: str):
        """移除 GPU 资源"""
        if gpu_id in self._resources:
            del self._resources[gpu_id]
            logger.info(f"已移除 GPU: {gpu_id}")

    async def submit_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        user_id: Optional[str] = None
    ) -> str:
        """提交训练任务"""
        task_id = f"{task_type}_{uuid.uuid4().hex[:8]}"

        task = TrainingTask(
            task_id=task_id,
            task_type=task_type,
            params=params,
            priority=priority,
            user_id=user_id
        )

        await self._queue.add(task)

        # 触发调度
        if self._running and self._dispatcher_task is None:
            self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

        return task_id

    async def _dispatch_loop(self):
        """任务分发循环"""
        while self._running:
            # 查找可用的 GPU
            available_gpu = self._find_available_gpu()

            if available_gpu:
                # 获取下一个任务
                task = await self._queue.get_next()

                if task:
                    # 分配 GPU
                    available_gpu.current_task_id = task.task_id
                    available_gpu.occupied_memory_mb = task.params.get("required_memory_mb", 1000)

                    # 启动任务执行
                    asyncio.create_task(self._execute_task(task, available_gpu))

            # 等待一段时间
            await asyncio.sleep(1)

    def _find_available_gpu(self) -> Optional[GPUResource]:
        """查找可用的 GPU"""
        for gpu in self._resources.values():
            if gpu.current_task_id is None:
                return gpu
        return None

    async def _execute_task(self, task: TrainingTask, gpu: GPUResource):
        """执行任务"""
        logger.info(f"开始执行任务: {task.task_id} on {gpu.gpu_id}")

        try:
            # 模拟任务执行
            # 实际使用时，这里应该调用真实的训练代码
            for progress in range(0, 101, 10):
                await asyncio.sleep(0.5)
                task.progress = progress / 100.0
                gpu.utilization = task.progress * 100

            # 模拟结果
            result = {"status": "success", "gpu": gpu.gpu_id}

            await self._queue.complete(task.task_id, result)

        except Exception as e:
            await self._queue.fail(task.task_id, str(e))

        finally:
            # 释放 GPU
            gpu.current_task_id = None
            gpu.occupied_memory_mb = 0
            gpu.utilization = 0

    async def start(self):
        """启动调度器"""
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        logger.info("GPU 调度器已启动")

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        logger.info("GPU 调度器已停止")

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self._queue.get_status(task_id)

    def get_gpu_status(self) -> List[Dict]:
        """获取 GPU 状态"""
        return [
            {
                "gpu_id": gpu.gpu_id,
                "name": gpu.name,
                "total_memory_mb": gpu.memory_mb,
                "used_memory_mb": gpu.occupied_memory_mb,
                "utilization": gpu.utilization,
                "in_use": gpu.current_task_id is not None,
                "current_task": gpu.current_task_id
            }
            for gpu in self._resources.values()
        ]

    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            "pending_tasks": self._queue.get_pending_count(),
            "running_tasks": self._queue.get_running_count(),
            "total_gpus": len(self._resources),
            "available_gpus": sum(1 for g in self._resources.values() if g.current_task_id is None)
        }

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return await self._queue.cancel(task_id)


# 全局调度器实例
gpu_scheduler = GPUScheduler()

# 添加默认 GPU（模拟）
gpu_scheduler.add_gpu("gpu_0", 8192, "NVIDIA GPU 0")
gpu_scheduler.add_gpu("gpu_1", 8192, "NVIDIA GPU 1")