"""
GPU 训练支持 - V2.2 深度学习策略引擎

包含:
- GPUManager: GPU 资源管理器
- CUDA 可用性检测和设备选择（cpu/cuda/mps）
- 多 GPU 训练支持（DataParallel）
- 混合精度训练（AMP - Automatic Mixed Precision）
- 显存管理和优化（梯度累积、梯度检查点）
- 训练速度基准测试
- 与现有 PricePredictor 和 DQNAgent 的集成
- GPU 资源监控（显存使用率、GPU 利用率）
"""
import logging
import time
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass

import torch
import torch.nn as nn
import numpy as np

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU 信息"""
    device_name: str
    device_index: int
    total_memory_mb: float
    used_memory_mb: float
    free_memory_mb: float
    utilization_percent: float
    is_available: bool


class GPUManager:
    """GPU 资源管理器

    提供 CUDA 可用性检测、设备选择、混合精度训练、
    多 GPU 支持和资源监控功能。
    """

    def __init__(self):
        self._device: Optional[torch.device] = None
        self._gpu_available: bool = False
        self._mps_available: bool = False
        self._cuda_available: bool = False
        self._gpu_count: int = 0
        self._device_names: List[str] = []
        self._amp_enabled: bool = False
        self._grad_checkpoint_enabled: bool = False
        self._grad_accumulation_steps: int = 1

        # 基准测试结果缓存
        self._benchmark_results: Dict[str, float] = {}

        # 初始化
        self._detect_devices()

    def _detect_devices(self):
        """检测可用设备"""
        # 检测 CUDA
        if torch.cuda.is_available():
            self._cuda_available = True
            self._gpu_available = True
            self._gpu_count = torch.cuda.device_count()
            self._device_names = [
                torch.cuda.get_device_name(i) for i in range(self._gpu_count)
            ]
            logger.info(f"CUDA 可用, GPU 数量: {self._gpu_count}, 设备: {self._device_names}")
        else:
            logger.info("CUDA 不可用")

        # 检测 MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            self._mps_available = True
            self._gpu_available = True
            logger.info("MPS (Apple Silicon) 可用")
        else:
            logger.info("MPS 不可用")

        # 设置默认设备
        self._device = self.get_optimal_device()

    def get_optimal_device(self) -> torch.device:
        """获取最优计算设备

        优先级: CUDA > MPS > CPU

        Returns:
            最优 torch.device
        """
        if self._cuda_available:
            return torch.device("cuda")
        elif self._mps_available:
            return torch.device("mps")
        else:
            return torch.device("cpu")

    def get_device(self, device_str: Optional[str] = None) -> torch.device:
        """获取指定设备

        Args:
            device_str: 设备字符串 (cpu/cuda/mps/auto)

        Returns:
            torch.device
        """
        if device_str is None or device_str == 'auto':
            return self._device

        device_str = device_str.lower().strip()
        if device_str == 'cuda' and self._cuda_available:
            return torch.device('cuda')
        elif device_str == 'mps' and self._mps_available:
            return torch.device('mps')
        elif device_str == 'cpu':
            return torch.device('cpu')
        else:
            logger.warning(f"设备 {device_str} 不可用，回退到 {self._device}")
            return self._device

    def enable_amp(self, enabled: bool = True):
        """启用/禁用混合精度训练

        Args:
            enabled: 是否启用
        """
        self._amp_enabled = enabled and self._cuda_available
        if enabled and not self._cuda_available:
            logger.warning("AMP 仅支持 CUDA，当前设备不支持")
        logger.info(f"混合精度训练 (AMP): {'启用' if self._amp_enabled else '禁用'}")

    def enable_gradient_checkpointing(self, enabled: bool = True):
        """启用/禁用梯度检查点

        Args:
            enabled: 是否启用
        """
        self._grad_checkpoint_enabled = enabled
        logger.info(f"梯度检查点: {'启用' if enabled else '禁用'}")

    def set_gradient_accumulation_steps(self, steps: int):
        """设置梯度累积步数

        Args:
            steps: 累积步数
        """
        self._grad_accumulation_steps = max(1, steps)
        logger.info(f"梯度累积步数: {self._grad_accumulation_steps}")

    def get_scaler(self):
        """获取 GradScaler（用于 AMP）

        Returns:
            torch.cuda.amp.GradScaler 或 None
        """
        if self._amp_enabled:
            return torch.amp.GradScaler(device='cuda')
        return None

    def to_device(self, model: nn.Module, device: Optional[str] = None) -> nn.Module:
        """将模型移到指定设备

        Args:
            model: PyTorch 模型
            device: 目标设备

        Returns:
            移动后的模型
        """
        target_device = self.get_device(device)

        if self._gpu_count > 1 and target_device.type == 'cuda':
            # 多 GPU 使用 DataParallel
            model = model.to(target_device)
            model = nn.DataParallel(model)
            logger.info(f"模型已使用 DataParallel 包装，GPU 数量: {self._gpu_count}")
        else:
            model = model.to(target_device)

        return model

    def apply_gradient_checkpointing(self, model: nn.Module) -> nn.Module:
        """对模型应用梯度检查点

        Args:
            model: PyTorch 模型

        Returns:
            应用了梯度检查点的模型
        """
        if not self._grad_checkpoint_enabled:
            return model

        # 对支持的模块应用梯度检查点
        for module in model.modules():
            if isinstance(module, (nn.TransformerEncoder, nn.TransformerDecoder)):
                module.gradient_checkpointing_enable()
                logger.debug("已对 Transformer 模块启用梯度检查点")

        return model

    def get_gpu_info(self) -> List[Dict]:
        """获取 GPU 信息

        Returns:
            GPU 信息列表
        """
        gpu_list = []

        if self._cuda_available:
            for i in range(self._gpu_count):
                try:
                    props = torch.cuda.get_device_properties(i)
                    allocated = torch.cuda.memory_allocated(i) / (1024 ** 2)
                    reserved = torch.cuda.memory_reserved(i) / (1024 ** 2)

                    info = {
                        'device_name': props.name,
                        'device_index': i,
                        'total_memory_mb': round(props.total_memory / (1024 ** 2), 2),
                        'used_memory_mb': round(allocated, 2),
                        'reserved_memory_mb': round(reserved, 2),
                        'free_memory_mb': round(props.total_memory / (1024 ** 2) - allocated, 2),
                        'is_available': True,
                        'compute_capability': f"{props.major}.{props.minor}",
                        'multiprocessor_count': props.multi_processor_count,
                    }

                    # 尝试获取 GPU 利用率（需要 pynvml）
                    try:
                        info['utilization_percent'] = self._get_gpu_utilization(i)
                    except Exception:
                        info['utilization_percent'] = -1

                    gpu_list.append(info)

                except Exception as e:
                    logger.error(f"获取 GPU {i} 信息失败: {e}")

        elif self._mps_available:
            gpu_list.append({
                'device_name': 'Apple Silicon (MPS)',
                'device_index': 0,
                'total_memory_mb': -1,  # MPS 不提供显存信息
                'used_memory_mb': -1,
                'free_memory_mb': -1,
                'is_available': True,
                'utilization_percent': -1,
            })

        if not gpu_list:
            gpu_list.append({
                'device_name': 'CPU',
                'device_index': -1,
                'total_memory_mb': 0,
                'used_memory_mb': 0,
                'free_memory_mb': 0,
                'is_available': False,
                'utilization_percent': -1,
            })

        return gpu_list

    def _get_gpu_utilization(self, device_index: int) -> float:
        """获取 GPU 利用率

        Args:
            device_index: GPU 设备索引

        Returns:
            GPU 利用率百分比
        """
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            pynvml.nvmlShutdown()
            return float(util.gpu)
        except ImportError:
            logger.debug("pynvml 未安装，无法获取 GPU 利用率")
            return -1.0
        except Exception as e:
            logger.debug(f"获取 GPU 利用率失败: {e}")
            return -1.0

    def get_memory_summary(self) -> Dict:
        """获取显存摘要

        Returns:
            显存摘要字典
        """
        if not self._cuda_available:
            return {
                'cuda_available': False,
                'device': str(self._device),
            }

        summary = {
            'cuda_available': True,
            'device': str(self._device),
            'gpu_count': self._gpu_count,
            'devices': [],
        }

        for i in range(self._gpu_count):
            allocated = torch.cuda.memory_allocated(i) / (1024 ** 2)
            reserved = torch.cuda.memory_reserved(i) / (1024 ** 2)
            peak_allocated = torch.cuda.max_memory_allocated(i) / (1024 ** 2)

            summary['devices'].append({
                'device_index': i,
                'allocated_mb': round(allocated, 2),
                'reserved_mb': round(reserved, 2),
                'peak_allocated_mb': round(peak_allocated, 2),
            })

        return summary

    def clear_cache(self):
        """清理 GPU 缓存"""
        if self._cuda_available:
            torch.cuda.empty_cache()
            logger.info("GPU 缓存已清理")
        elif self._mps_available:
            torch.mps.empty_cache()
            logger.info("MPS 缓存已清理")

    def run_benchmark(self, model: Optional[nn.Module] = None,
                      input_size: Optional[Tuple] = None,
                      num_iterations: int = 100) -> Dict:
        """运行训练速度基准测试

        Args:
            model: 测试模型（None 则使用默认模型）
            input_size: 输入尺寸 (batch, features)
            num_iterations: 迭代次数

        Returns:
            基准测试结果
        """
        device = self._device

        # 创建默认测试模型
        if model is None:
            if input_size is None:
                input_size = (32, 64)
            model = nn.Sequential(
                nn.Linear(input_size[1], 256),
                nn.ReLU(),
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Linear(128, 3),
            )

        model = model.to(device)
        model.train()

        # 创建测试输入
        if input_size is None:
            input_size = (32, 64)
        x = torch.randn(input_size).to(device)
        y = torch.randint(0, 3, (input_size[0],)).to(device)

        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

        # 预热
        for _ in range(10):
            optimizer.zero_grad()
            output = model(x)
            loss = criterion(output, y)
            loss.backward()
            optimizer.step()

        # 正式测试
        if self._cuda_available:
            torch.cuda.synchronize()

        start_time = time.time()

        for _ in range(num_iterations):
            optimizer.zero_grad()

            if self._amp_enabled:
                scaler = self.get_scaler()
                with torch.amp.autocast(device_type='cuda'):
                    output = model(x)
                    loss = criterion(output, y)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                output = model(x)
                loss = criterion(output, y)
                loss.backward()
                optimizer.step()

        if self._cuda_available:
            torch.cuda.synchronize()

        elapsed = time.time() - start_time
        avg_time_ms = (elapsed / num_iterations) * 1000
        throughput = num_iterations / elapsed

        result = {
            'device': str(device),
            'device_name': self._device_names[0] if self._device_names else 'CPU',
            'amp_enabled': self._amp_enabled,
            'batch_size': input_size[0],
            'input_features': input_size[1],
            'num_iterations': num_iterations,
            'total_time_seconds': round(elapsed, 4),
            'avg_iteration_time_ms': round(avg_time_ms, 4),
            'throughput_iterations_per_sec': round(throughput, 2),
            'model_parameters': sum(p.numel() for p in model.parameters()),
        }

        # 获取显存使用
        if self._cuda_available:
            result['peak_memory_mb'] = round(
                torch.cuda.max_memory_allocated() / (1024 ** 2), 2
            )
            torch.cuda.reset_peak_memory_stats()

        self._benchmark_results[str(device)] = avg_time_ms

        logger.info(
            f"基准测试完成: 设备={device}, "
            f"平均耗时={avg_time_ms:.2f}ms, "
            f"吞吐量={throughput:.1f} iter/s"
        )

        return result

    def get_status(self) -> Dict:
        """获取 GPU 管理器状态

        Returns:
            状态字典
        """
        return {
            'device': str(self._device),
            'cuda_available': self._cuda_available,
            'mps_available': self._mps_available,
            'gpu_available': self._gpu_available,
            'gpu_count': self._gpu_count,
            'device_names': self._device_names,
            'amp_enabled': self._amp_enabled,
            'gradient_checkpointing_enabled': self._grad_checkpoint_enabled,
            'gradient_accumulation_steps': self._grad_accumulation_steps,
            'gpu_info': self.get_gpu_info(),
            'memory_summary': self.get_memory_summary(),
            'benchmark_results': self._benchmark_results,
        }


# 全局 GPU 管理器实例
gpu_manager = GPUManager()
