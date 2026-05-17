"""
强化学习训练 API

提供 RL 策略的训练和评估接口。
"""

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from .rl_trading_env import TradingEnvironment, MultiAssetTradingEnvironment
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/ml/rl", tags=["reinforcement_learning"])

logger = logging.getLogger(__name__)


class RLEnvConfig(BaseModel):
    """RL 环境配置"""
    prices: List[float] = Field(..., description="价格序列")
    initial_cash: float = Field(10000.0, description="初始资金")
    transaction_cost: float = Field(0.001, description="交易成本")
    window_size: int = Field(10, ge=3, le=60, description="价格窗口大小")
    discrete_actions: bool = Field(True, description="是否使用离散动作")
    reward_type: str = Field("returns", description="奖励类型: returns/portfolio")


class RLTrainRequest(BaseModel):
    """RL 训练请求"""
    env_config: RLEnvConfig
    algo: str = Field("dqn", description="算法: dqn/ppo/a2c")
    n_episodes: int = Field(100, ge=1, le=1000, description="训练回合数")
    max_steps: int = Field(1000, description="每回合最大步数")
    learning_rate: float = Field(0.001, description="学习率")
    gamma: float = Field(0.99, description="折扣因子")


class RLEvaluateRequest(BaseModel):
    """RL 评估请求"""
    env_config: RLEnvConfig
    policy: Dict[str, Any] = Field(..., description="策略参数")


class RLActionResponse(BaseModel):
    """动作响应"""
    action: int
    action_name: str
    expected_reward: Optional[float] = None


class RLTrainResponse(BaseModel):
    """训练响应"""
    episode: int
    total_reward: float
    portfolio_value: float
    sharpe_ratio: float
    max_drawdown: float
    steps: int


@router.post("/env/validate")
def validate_env(
    config: RLEnvConfig,
    current_user: dict = Depends(get_current_user)
):
    """
    验证环境配置

    检查价格数据和配置参数是否有效。
    """
    prices = np.array(config.prices)

    issues = []

    if len(prices) < config.window_size * 2:
        issues.append(f"价格数据长度 ({len(prices)}) 少于窗口大小的两倍")

    if config.initial_cash <= 0:
        issues.append("初始资金必须大于 0")

    if config.transaction_cost < 0 or config.transaction_cost > 0.1:
        issues.append("交易成本应在 0-10% 之间")

    if len(prices) == 0:
        issues.append("价格数据为空")

    # 计算基本统计
    stats = {
        "n_prices": len(prices),
        "mean_price": float(np.mean(prices)) if len(prices) > 0 else 0,
        "std_price": float(np.std(prices)) if len(prices) > 0 else 0,
        "min_price": float(np.min(prices)) if len(prices) > 0 else 0,
        "max_price": float(np.max(prices)) if len(prices) > 0 else 0,
    }

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "stats": stats
    }


@router.post("/env/reset")
def reset_env(
    config: RLEnvConfig,
    current_user: dict = Depends(get_current_user)
):
    """
    重置 RL 环境

    返回初始观察。
    """
    try:
        prices = np.array(config.prices)
        env = TradingEnvironment(
            prices=prices,
            initial_cash=config.initial_cash,
            transaction_cost=config.transaction_cost,
            window_size=config.window_size,
            discrete_actions=config.discrete_actions,
            reward_type=config.reward_type
        )

        observation = env.reset()

        return {
            "observation": observation.tolist(),
            "action_space": {
                "type": "discrete" if config.discrete_actions else "continuous",
                "n": env.action_space.n if config.discrete_actions else env.action_space.shape[0]
            },
            "observation_shape": observation.shape[0]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/env/step")
def step_env(
    config: RLEnvConfig,
    action: int = Field(..., description="动作 (0=卖出, 1=持有, 2=买入)"),
    current_user: dict = Depends(get_current_user)
):
    """
    执行一步

    在 RL 环境中执行指定动作。
    """
    try:
        prices = np.array(config.prices)
        env = TradingEnvironment(
            prices=prices,
            initial_cash=config.initial_cash,
            transaction_cost=config.transaction_cost,
            window_size=config.window_size,
            discrete_actions=config.discrete_actions,
            reward_type=config.reward_type
        )

        # 重置环境
        env.reset()

        # 执行指定步数
        for _ in range(10):  # 先走几步
            _, _, done, _ = env.step(1)  # 持有
            if done:
                break

        # 执行指定动作
        observation, reward, done, info = env.step(action)

        action_names = {0: "卖出", 1: "持有", 2: "买入"}

        return {
            "observation": observation.tolist(),
            "reward": float(reward),
            "done": done,
            "info": info,
            "action_name": action_names.get(action, "未知")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulate")
def simulate_trading(
    config: RLEnvConfig,
    actions: List[int] = Field(..., description="动作序列"),
    current_user: dict = Depends(get_current_user)
):
    """
    模拟交易

    给定动作序列，模拟交易结果。
    """
    try:
        prices = np.array(config.prices)
        env = TradingEnvironment(
            prices=prices,
            initial_cash=config.initial_cash,
            transaction_cost=config.transaction_cost,
            window_size=config.window_size,
            discrete_actions=config.discrete_actions,
            reward_type=config.reward_type
        )

        env.reset()

        episode_rewards = []
        episode_info = []

        for action in actions:
            obs, reward, done, info = env.step(action)
            episode_rewards.append(reward)
            episode_info.append(info)

            if done:
                break

        return {
            "n_steps": len(episode_rewards),
            "total_reward": float(sum(episode_rewards)),
            "mean_reward": float(np.mean(episode_rewards)) if episode_rewards else 0,
            "final_portfolio_value": episode_info[-1]["portfolio_value"] if episode_info else config.initial_cash,
            "sharpe_ratio": float(env.sharpe_ratio),
            "max_drawdown": float(env.max_drawdown),
            "history": episode_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/algorithms")
def list_algorithms():
    """
    获取支持的 RL 算法列表

    注意: 实际训练需要 Stable-Baselines3 库。
    当前接口仅提供配置信息。
    """
    return {
        "algorithms": [
            {
                "id": "dqn",
                "name": "Deep Q-Network",
                "description": "适用于离散动作空间，适合入门",
                "action_type": "discrete"
            },
            {
                "id": "ppo",
                "name": "Proximal Policy Optimization",
                "description": "适用于连续/离散动作，稳定性好",
                "action_type": "both"
            },
            {
                "id": "a2c",
                "name": "Advantage Actor-Critic",
                "description": "同步版本的 A3C，效率高",
                "action_type": "both"
            }
        ],
        "note": "实际训练需要安装 stable-baselines3: pip install stable-baselines3"
    }