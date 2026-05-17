# OpenClaw 量化交易框架 - 5分钟快速入门

> 专为小白设计的入门指南，5分钟让你跑通第一个策略

## 前置要求

- Docker Desktop（[macOS下载](https://docs.docker.com/docker-for-mac/install/) / [Windows下载](https://docs.docker.com/docker-for-windows/install/)）
- 4GB+ 可用内存

## 第一步：一键启动（1分钟）

```bash
# 1. 进入项目目录
cd quant-framework

# 2. 一键启动
./start.sh
```

等待出现以下信息表示启动成功：
```
==========================================
  启动成功！
==========================================
  访问地址：
    前端界面: http://localhost
    API 文档: http://localhost:8000/docs
```

## 第二步：打开界面（1分钟）

在浏览器中打开：

| 页面 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost | Dashboard 仪表盘 |
| API 文档 | http://localhost:8000/docs | 所有 API 接口说明 |

登录账号：`admin` / `admin123`

## 第三步：运行选股（2分钟）

1. 点击左侧菜单 **"选股"**
2. 点击 **"生成信号"** 按钮
3. 等待几秒，查看选股结果

系统会根据内置策略筛选出符合条件的股票，每条信号会显示：
- 股票代码和名称
- 入选理由（为什么选中这只股票）
- 预计买入价格
- 风控评分

## 第四步：查看回测（1分钟）

1. 点击左侧菜单 **"回测"**
2. 点击 **"运行回测"**
3. 查看收益曲线和统计指标

| 指标 | 说明 |
|------|------|
| 年化收益 | 一年下来的平均收益率 |
| 最大回撤 | 历史最大亏损幅度 |
| 夏普比率 | 风险调整后的收益 |
| 胜率 | 盈利交易占比 |

## 常见问题

### Q: 启动脚本报错"权限不足"
```bash
chmod +x start.sh stop.sh reset.sh
```

### Q: 端口被占用
```bash
# 检查哪个进程占用了端口
lsof -i:3306
lsof -i:8000
lsof -i:80

# 结束占用进程或修改 docker-compose.yml 中的端口映射
```

### Q: 页面打不开
```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### Q: 选股没有结果
这是正常的，可能的原因：
1. 当前市场没有符合条件的股票
2. 还未到交易时间（A 股需要在交易日 15:00 后）
3. 未配置数据源 Token（见下方"可选配置"）

## 可选配置

### 配置数据源 Token（获取更多数据）

1. 编辑 `.env` 文件：
```bash
nano .env
```

2. 填写以下 Token（可选但推荐）：
```env
# AKShare（免费，https://akshare.akfamily.xyz/）
AK_SHARE_TOKEN=

# TuShare（收费，https://tushare.pro/）
TUSHARE_TOKEN=
```

3. 重启服务：
```bash
./stop.sh && ./start.sh
```

### 配置实盘交易

如需连接实盘，请参考 [TUTORIAL.md](TUTORIAL.md) 中的"实盘对接"章节。

## 下一步

- [完整使用教程](TUTORIAL.md) - 深入学习所有功能
- [API 文档](http://localhost:8000/docs) - 开发者接口
- [ROADMAP.md](ROADMAP.md) - 了解项目规划

## 技术支持

- GitHub Issues: https://github.com/your-repo/issues
- 文档: ./docs/