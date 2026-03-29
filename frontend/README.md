# OpenClaw 量化交易监控前端

基于 Vue 3 + Vite + Element Plus 开发的量化交易监控面板。

## 功能

- **仪表盘**：展示当前持仓、今日交易信号、绩效统计概览
- **选股结果**：按日期查询每日选股结果，支持筛选和分页
- **交易记录**：历史交易记录查询，支持多条件筛选
- **系统日志**：系统日志实时查看，支持自动刷新和筛选

## 技术栈

- Vue 3 (Composition API + setup)
- Vite
- Element Plus
- Pinia 状态管理
- Vue Router
- Axios
- ECharts 图表

## 开发

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

服务运行在 `http://localhost:3000`

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 配置

复制 `.env.example` 到 `.env`，修改 API 地址：

```
VITE_API_BASE_URL=http://your-backend-host:8000
```

## 后端API对接

前端已对接后端API接口，详见后端 `docs/API接口文档.md`

- 所有API基础路径 `/api/v1`
- 开发环境通过Vite代理转发 `/api` -> `http://localhost:8000`

## 页面结构

```
src/
├── main.js          # 入口文件
├── App.vue          # 根组件（布局）
├── router/          # 路由配置
├── api/             # API接口封装
├── stores/          # Pinia状态管理
├── views/           # 页面组件
│   ├── Dashboard.vue   # 仪表盘
│   ├── Selections.vue  # 选股结果
│   ├── Trades.vue      # 交易记录
│   └── Logs.vue        # 系统日志
└── assets/styles/  # 全局样式
```

## 开发说明

- 使用 Composition API + setup script 风格
- 盈亏颜色约定：红色(profit-positive)表示盈利，绿色(profit-negative)表示亏损（A股市场习惯）
- 所有列表都支持分页加载
- 自动适配响应式布局
