# OpenClaw 量化交易框架 — 变更日志

> 所有重要变更均记录在此文件中。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

---

## [2.0.1] - 2026-04-02

### 修复 (Bug Fixes)
- **健康检查**: 修复 SQLAlchemy 2.x 兼容性问题，`db.execute("SELECT 1")` 改为 `db.execute(text("SELECT 1"))`
- **ShareView**: 修复 `apiExportProject` 导入名称错误，改为 `exportProject`
- **Logs.vue**: 替换清空日志的 `setTimeout` 模拟为真实 API 调用

### 新增 (Added)
- **插件系统**: 实现核心执行引擎，支持钩子模式 (`fire_hook`) 和直接执行模式 (`register_executor`)
- **项目管理 API**: 新增 10 个端点（导出历史、分享链接、访问统计、权限管理等）
- **数据模型**: 新增 `ProjectExport`、`ShareLink`、`AccessLog` 三张表
- **清空日志 API**: 新增 `DELETE /api/v1/logs` 端点

### 变更 (Changed)
- **安全加固**: CORS 默认值从 `["*"]` 改为开发环境白名单
- **安全加固**: `TrustedHostMiddleware` 的 `allowed_hosts` 改为从配置读取
- **ShareView.vue**: 9 个 TODO 全部对接后端 API（导出历史、下载、删除、权限、分享链接、访问统计等）

---

## [2.0.0] - 2026-04-01

### 新增 (Added)
- **AI 智能分析助手 (V1.5)**: LLM 抽象层（OpenAI/DeepSeek/Ollama）、情感分析、异常检测、策略归因
- **社区与协作 (V1.6)**: 讨论帖、交易分享、排行榜、私信功能
- **多市场扩展 (V1.7)**: 期货、加密货币、ETF、套利机会，对接 Binance + akshare 真实数据
- **高可用与灾备 (V1.8)**: 集群监控、数据库备份、告警规则、Grafana 仪表板
- **算法交易增强 (V1.9)**: TWAP/VWAP/冰山/智能路由算法引擎
- **平台化 (V2.0)**: 多租户、插件系统、计费系统、开放 API、Python/JavaScript SDK
- **前端**: 新增 8 个页面视图（AI助手、社区、多市场、算法交易、HA监控、租户管理、插件市场、计费管理）
- **部署**: Docker Compose HA 配置、备份/健康检查脚本、Prometheus + Grafana 监控栈
- **数据库**: 新增 30 张表，2 个 Alembic 迁移文件
- **测试**: 71 个单元测试

---

## [1.4.0] - 2026-03-30

### 新增 (Added)
- 移动端适配（响应式布局 + PWA 支持）
- 3D 建模视图模块（Three.js）

---

## [1.3.0] - 2026-03-29

### 新增 (Added)
- 多账户管理与风控增强
- 综合风控管理器（A股 + 期权 + 全局风控）

---

## [1.2.0] - 2026-03-28

### 新增 (Added)
- 高级期权策略（Long Call/Put、跨式、价差等 6 种）
- 期权策略选择器与引擎

---

## [1.1.0] - 2026-03-27

### 新增 (Added)
- 策略市场（模板创建、安装、预览）
- 项目分享与协作功能

---

## [1.0.0] - 2026-03-26

### 新增 (Added)
- 生产发布就绪
- 回测可视化

---

## [0.9.0] - 2026-03-25

### 新增 (Added)
- 回测引擎（佣金、印花税、滑点模拟）
- 回测报告生成（年化收益、最大回撤、夏普比率、胜率）

---

## [0.8.0] - 2026-03-24

### 新增 (Added)
- 实时数据推送（WebSocket）
- 通知系统（微信/钉钉/邮件）

---

## [0.7.0] - 2026-03-23

### 新增 (Added)
- 数据库迁移（Alembic）
- JWT 认证授权系统

---

## [0.6.0] - 2026-03-22

### 新增 (Added)
- FMZ 实盘对接
- FMZ API 数据模型

---

## [0.5.0] - 2026-03-21

### 变更 (Changed)
- 前后端联调与 Bug 修复

---

## [0.4.0] - 2026-03-20

### 新增 (Added)
- 机器学习策略（GBM/RandomForest + Optuna 超参数优化）
- 因子提取器（51 个因子）
- SHAP 可解释性分析

---

## [0.3.0] - 2026-03-19

### 新增 (Added)
- 三市场数据采集（A股/港股/美股，akshare）
- APScheduler 定时调度器

---

## [0.2.0] - 2026-03-18

### 新增 (Added)
- A股尾盘选股策略（14步筛选 + 评分排序）
- 港美股事件驱动策略
- 综合风控管理器

---

## [0.1.0] - 2026-03-17

### 新增 (Added)
- 项目骨架搭建（backend / frontend / docs / deploy）
- 数据库模型（7 张表）
- FastAPI 后端 API 框架
- Vue 3 前端框架（Element Plus + ECharts + Pinia）
- Docker Compose 部署配置
- CI/CD 流水线（GitHub Actions）
- Prometheus + Grafana 监控栈
