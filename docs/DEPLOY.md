# OpenClaw量化交易框架 - 部署文档

本项目采用 Docker + Docker-Compose 容器化部署，支持一键拉起全栈服务。

## 目录结构

```
quant-framework/
├── backend/              # 后端API服务
│   └── Dockerfile
├── frontend/             # 前端监控面板
│   ├── Dockerfile
│   └── nginx.conf
├── docs/                 # 文档
├── src/                  # 核心策略代码
├── tests/                # 测试代码
├── deploy/               # 部署相关配置
│   ├── prometheus/       # Prometheus监控配置
│   ├── alertmanager/     # 告警配置
│   ├── docker-compose.monitoring.yml
│   └── logrotate.conf
├── .github/workflows/    # GitHub Actions CI/CD
├── docker-compose.yml    # 主服务编排
├── .env.example          # 环境变量示例
└── README.md
```

## 系统要求

- Docker 20.x+
- Docker Compose v2+
- 至少 2核4GB 内存（开发环境可降低）
- 10GB+ 磁盘空间

---

## 开发环境部署

### 1. 克隆代码

```bash
git clone <your-repo-url>
cd quant-framework
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env
```

根据你的需求修改环境变量：
- `DEBUG=true` 开启调试模式
- `MYSQL_*` 修改数据库密码等配置
- 填写 `TUSHARE_TOKEN` / `AK_SHARE_TOKEN` 数据API Token
- 填写 `FMZ_API_KEY` / `FMZ_SECRET_KEY` / `FMZ_CID` FMZ发明者量化平台密钥

### 3. 一键启动

```bash
docker-compose up -d
```

这个命令会自动：
- 构建后端镜像
- 构建前端镜像
- 启动 MySQL 数据库
- 启动后端API服务（端口 `8000`）
- 启动前端仪表盘（端口 `80`）

### 4. 查看状态

```bash
docker-compose ps
```

### 5. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 只看后端日志
docker-compose logs -f backend

# 只看数据库日志
docker-compose logs -f db
```

### 6. 访问服务

- 前端仪表盘：`http://localhost`
- 后端API文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 7. 停止服务

```bash
docker-compose down
# 保留数据，如果需要清理数据请执行：
# docker-compose down -v
```

---

## 生产环境部署

### 前置准备

1. 已经配置好域名解析到你的服务器
2. 服务器已开放 80, 443 端口
3. 准备好SSL证书（推荐使用Let's Encrypt免费证书）

### 1. 克隆代码到服务器

```bash
git clone <your-repo-url>
cd quant-framework
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env
```

**重要生产环境配置修改：**
- `DEBUG=false`
- 修改 `MYSQL_ROOT_PASSWORD` 和 `MYSQL_PASSWORD` 为强密码
- 修改 `CORS_ORIGIN` 为你的实际域名，比如 `https://quant.yourdomain.com`
- 确保填入正确的 FMZ API 密钥

### 3. 配置反向代理（Nginx + SSL）

推荐使用 Nginx 作为反向代理并配置 SSL：

```nginx
server {
    listen 80;
    server_name quant.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name quant.yourdomain.com;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # 前端
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API 反向代理
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # OpenAPI文档
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
    }
}
```

### 4. 启动服务

```bash
docker-compose up -d
```

首次启动需要等待数据库初始化，大约1-2分钟。

### 5. 验证部署

```bash
# 检查容器状态
docker-compose ps

# 检查健康状态
curl http://localhost:8000/health
# 应该返回 {"status":"ok"}
```

### 6. 更新部署

当代码更新后，执行以下命令更新：

```bash
cd /path/to/quant-framework
git pull origin main
docker-compose build
docker-compose up -d --force-recreate
docker system prune -f  # 清理旧镜像
```

---

## 本地开发（不用Docker）

如果你想直接在本地开发，可以按以下步骤：

### 后端开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 修改配置
cp .env.example .env
vim .env

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
```

### 运行测试

```bash
cd tests
pytest -v --asyncio-mode=auto
```

---

## CI/CD 配置

本项目使用 GitHub Actions 实现自动化测试、构建、部署。

### 需要配置的 GitHub Secrets

进入你的 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | 说明 |
|-------------|------|
| `SERVER_HOST` | 你的生产服务器IP |
| `SERVER_PORT` | SSH端口（默认22）|
| `SERVER_USER` | SSH用户名 |
| `SERVER_SSH_KEY` | SSH私钥内容 |
| `DEPLOY_PATH` | 服务器上的部署路径，比如 `/opt/quant-framework` |
| `SLACK_WEBHOOK` | Slack webhook地址用于通知（可选）|

配置完成后，每当推送到 `main` 分支，就会自动：
1. 运行测试
2. 构建后端和前端 Docker 镜像并推送到 GHCR (GitHub Container Registry)
3. SSH 连接到生产服务器拉取最新镜像并重启服务

---

## 日志管理

### 日志位置

容器内日志：
- 后端日志：`/app/logs/`
- 挂载到宿主机：`./logs/` 目录

### 配置日志轮转

将提供的 `logrotate.conf` 安装到 `/etc/logrotate.d/`：

```bash
sudo cp deploy/logrotate.conf /etc/logrotate.d/quant-framework
sudo systemctl reload logrotate
```

默认配置：
- 每天轮转一次
- 保留30天日志
- 自动压缩旧日志

---

## 监控与告警

本项目提供 Prometheus + Grafana + AlertManager 监控方案。

### 启动监控

```bash
# 确保主服务已经启动，然后执行：
cd deploy
docker-compose -f docker-compose.monitoring.yml up -d
```

监控组件：
- Prometheus：端口 `9090` - 指标收集存储
- Grafana：端口 `3000` - 可视化仪表盘（默认账号 admin/admin）
- AlertManager：端口 `9093` - 告警管理
- Node Exporter：端口 `9100` - 主机监控
- MySQL Exporter：端口 `9104` - MySQL监控

### 配置告警

编辑 `deploy/alertmanager/alertmanager.yml`，填入你的告警渠道：

支持：
- 企业微信
- 钉钉
- Webhook（可对接飞书等）
- Slack

预设告警规则：
1. **BackendDown** - 后端服务不可用（>1分钟）→ 严重
2. **DatabaseDown** - 数据库不可用（>1分钟）→ 严重
3. **HighCPUUsage** - CPU使用率 >80%（>5分钟）→ 警告
4. **LowDiskSpace** - 磁盘剩余 <10%（>5分钟）→ 警告
5. **HighErrorRate** - API 5xx错误率 >5%（>2分钟）→ 警告

### 添加Grafana仪表盘

1. 登录 Grafana
2. 添加 Prometheus 数据源：`http://prometheus:9090`
3. 导入以下仪表盘：
   - Node Exporter Full (ID: 1860) - 主机监控
   - MySQL Overview (ID: 11323) - MySQL监控

---

## 数据备份

### 自动备份MySQL

创建备份脚本 `backup.sh`：

```bash
#!/bin/bash
BACKUP_DIR=/path/to/backups
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker exec quant-db mysqldump -uquant -p'quant123456' quant_trade | gzip > $BACKUP_DIR/quant_trade_$DATE.sql.gz

# 保留30天备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

添加到crontab每天备份：

```
0 2 * * * /path/to/backup.sh
```

---

## 常见问题

### 1. 容器启动后数据库连接失败

**原因**：数据库还没完成初始化，后端就启动了。

**解决**：稍等几十秒，后端会自动重连，或者重启后端：
```bash
docker-compose restart backend
```

### 2. 前端无法连接API

**原因**：CORS配置不正确。

**解决**：检查 `.env` 中的 `CORS_ORIGIN` 是否正确设置为你的域名。

### 3. 如何重置数据库

**危险操作**：这会删除所有数据
```bash
docker-compose down -v
docker-compose up -d
```

### 4. 查看数据库

```bash
docker exec -it quant-db mysql -uquant -p quant_trade
```

---

## 性能调优

### MySQL配置

对于生产环境，可以在 `docker-compose.yml` 中添加自定义配置：

```yaml
db:
  image: mysql:8.0
  command: --default-authentication-plugin=mysql_native_password --innodb-buffer-pool-size=256M --max-connections=200
```

### 后端启动优化

可以使用 Gunicorn 替代 Uvicorn 生产部署，在 `backend/Dockerfile` 修改启动命令：

```dockerfile
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

---

## 端口说明

| 服务 | 默认端口 | 说明 |
|------|---------|------|
| 前端 | 80 | HTTP服务 |
| 后端API | 8000 | FastAPI服务 |
| MySQL | 3306 | 数据库 |
| Prometheus | 9090 | 监控指标存储 |
| Grafana | 3000 | 监控仪表盘 |
| AlertManager | 9093 | 告警管理 |

## License

MIT
