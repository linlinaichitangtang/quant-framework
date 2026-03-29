# 项目结构说明

```
quant-framework/
├── README.md                     # 项目总介绍
├── README_ML_STRATEGY.md        # 机器学习A股尾盘策略说明
├── PROJECT_STRUCTURE.md         # 本文件，项目结构说明
├── requirements.txt             # Python依赖
├── docker-compose.yml           # Docker compose配置（可选）
├── Dockerfile                   # Docker镜像定义（可选）
├── .env.example                 # 环境变量示例
├── run_demo.py                  # 基础版策略演示
├── run_demo_fast.py             # 基础版快速演示
├── run_ml_strategy.py           # 机器学习策略主入口
├── debug_*.py                   # 调试测试脚本
├── src/                         # 核心源代码
│   ├── __init__.py
│   ├── strategies/              # 策略实现
│   │   ├── __init__.py
│   │   ├── a_stock_evening.py           # 基础版A股尾盘规则策略
│   │   └── a_stock_evening_ml.py        # 进阶版机器学习尾盘策略
│   ├── api/                     # API接口模块
│   │   ├── __init__.py
│   │   └── fmz_api.py                   # FMZ API客户端定义
│   ├── risk/                    # 风控模块
│   │   ├── __init__.py
│   │   └── risk_manager.py              # 综合风控管理器
│   ├── data/                    # 数据处理模块
│   │   ├── __init__.py
│   │   ├── tushare_provider.py          # Tushare数据获取
│   │   ├── factors.py                   # 量价因子计算
│   │   └── cache.py                     # 数据缓存管理
│   ├── ml/                      # 机器学习模块
│   │   ├── __init__.py
│   │   ├── model.py                     # 模型定义（随机森林）
│   │   ├── trainer.py                   # 滚动训练 + Optuna超参数优化
│   │   └── predictor.py                 # 预测 + SHAP可解释性分析
│   ├── backtest/                # 回测模块（第二阶段）
│   │   ├── __init__.py
│   │   ├── bt_strategy.py               # backtrader策略类
│   │   ├── engine.py                    # 回测引擎封装
│   │   └── analyzer.py                  # 回测结果分析
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── logging.py            # 日志配置
│       └── helpers.py            # 通用助手
├── tests/                        # 单元测试
├── docs/                         # 文档
├── examples/                     # 使用示例
├── storage/                      # 运行时存储（git忽略）
│   ├── cache/                   # 行情数据缓存
│   ├── models/                  # 训练好的模型保存
│   ├── output/                  # 回测结果、SHAP图表
│   └── logs/                    # 日志文件
└── output_demo/                 # 示例输出（提交git方便查看）
```

## 开发流程

### 第一阶段：策略开发与本地回测
1. 在 `src/strategies/` 实现具体策略
2. 在 `src/ml/` 实现机器学习训练和预测
3. 通过 `run_ml_strategy.py` 运行回测
4. 根据回测结果优化参数和规则

### 第二阶段：AI动态决策回测（backtrader集成）
1. 在 `src/backtest/` 实现 backtrader 策略
2. 每日调用 OpenClaw API 获取决策
3. 严格避免未来函数，真实模拟实盘决策
4. 分析回测绩效，持续优化

## 架构设计

- **决策与执行分离**：OpenClaw 负责选股和决策，FMZ 负责实盘执行
- **数据流**：`市场数据 → 策略计算 → 风控 → 交易信号 → FMZ API → 执行 → 结果返回`
- **可扩展性**：基于基类设计，方便添加新策略、新数据源、新风控规则

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填写 TUSHARE_TOKEN、FMZ_API_URL 等
```

3. 运行机器学习尾盘策略回测
```bash
python run_ml_strategy.py
```

4. 查看回测结果和SHAP图表，输出到 `storage/output/`
