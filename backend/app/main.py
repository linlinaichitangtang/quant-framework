import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from .config import settings
from .database import engine, Base, SessionLocal
from .cache import init_cache
from .api import router
from .auth_api import router as auth_router
from .ws_api import router as ws_router
from .backtest_api import router as backtest_router
from .template_api import router as template_router
from .options_api import router as options_router
from .account_api import router as account_router
from .ai_api import router as ai_router
from .tenant_api import router as tenant_router
from .plugin_api import router as plugin_router
from .billing_api import router as billing_router
from .open_api import router as open_api_router
from .ha_api import router as ha_router
from .algo_api import router as algo_router
from .multi_market_api import router as multi_market_router
from .community_api import router as community_router


# ========== 结构化日志配置 ==========
def setup_logging():
    """配置全局结构化日志"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # JSON 格式化器（生产）或纯文本格式化器（开发）
    if not settings.debug:
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
            )
        except ImportError:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # 降低第三方库日志级别
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error",
                  "sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool",
                  "apscheduler", "matplotlib", "PIL",
                  "urllib3", "httpx", "httpcore",
                  "slowapi", "prometheus_client"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    return logging.getLogger(__name__)


logger = setup_logging()

# ========== 创建数据库表 ==========
Base.metadata.create_all(bind=engine)

# ========== API 限流 ==========
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


# ========== 应用生命周期 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    from . import crud

    # 初始化缓存
    init_cache(settings.redis_url)

    # 初始化默认管理员
    db = SessionLocal()
    try:
        admin = crud.init_default_admin(db)
        if admin:
            logger.info("默认管理员账户已创建")
        else:
            logger.debug("管理员账户已存在")
    finally:
        db.close()

    # 初始化默认订阅计划
    try:
        from .billing_service import BillingService
        billing = BillingService(db)
        billing.init_default_plans(db)
        logger.info("默认订阅计划已初始化")
    except Exception as e:
        logger.warning(f"订阅计划初始化失败: {e}")

    logger.info(f"{settings.app_name} v{settings.app_version} 启动完成 (debug={settings.debug})")

    yield

    # 关闭
    from .cache import get_cache
    get_cache().close()
    logger.info("应用已关闭")


# ========== 创建 FastAPI 应用 ==========
tags_metadata = [
    {"name": "核心交易", "description": "股票信息、行情数据、持仓管理、交易信号、交易记录"},
    {"name": "FMZ 执行", "description": "FMZ 发明者量化平台对接、信号执行、机器人管理"},
    {"name": "认证授权", "description": "用户注册、登录、Token 管理、权限控制"},
    {"name": "WebSocket", "description": "实时行情推送、交易通知、系统告警"},
    {"name": "回测分析", "description": "策略回测、回测结果查询、交易明细"},
    {"name": "策略模板", "description": "策略模板管理、模板市场、安装与评分"},
    {"name": "期权分析", "description": "期权链查询、希腊字母计算、组合策略分析"},
    {"name": "账户风控", "description": "交易账户管理、风控规则配置、风控事件监控"},
    {"name": "AI 智能分析", "description": "AI 对话、市场情绪分析、异常交易检测、策略归因、自然语言查询"},
    {"name": "多租户管理", "description": "租户 CRUD、白标配置、用量统计（管理员）"},
    {"name": "插件市场", "description": "插件发布、安装、执行、评分"},
    {"name": "计费管理", "description": "订阅计划、订阅管理、用量统计、账单查询"},
    {"name": "开放 API", "description": "第三方系统对接的开放接口（API Key 认证）"},
    {"name": "高可用与灾备", "description": "集群管理、数据库复制、备份恢复、系统监控、告警管理"},
    {"name": "算法交易", "description": "TWAP/VWAP/冰山/智能拆单等算法交易策略"},
    {"name": "多市场扩展", "description": "期货、加密货币、ETF、跨市场套利、全球时区"},
]

app = FastAPI(
    title="OpenClaw 量化交易平台 API",
    description=(
        "OpenClaw 量化交易平台 — 集成智能决策、FMZ 执行、AI 分析、多租户管理的全栈量化交易解决方案\n\n"
        "## 核心交易模块\n"
        "- A 股 / 港股 / 美股行情数据与股票信息管理\n"
        "- 持仓管理与交易信号生成\n"
        "- FMZ 发明者量化平台实盘对接与自动执行\n\n"
        "## 认证与安全\n"
        "- JWT / API Key 双重认证机制\n"
        "- 基于角色的权限控制（公开 / 认证 / 管理员）\n"
        "- API 限流与安全响应头\n\n"
        "## 实时数据推送\n"
        "- WebSocket 实时行情、信号、交易通知\n"
        "- 多渠道通知（企业微信 / 钉钉 / 邮件）\n\n"
        "## 回测与策略\n"
        "- 策略回测引擎（佣金 / 印花税 / 滑点模拟）\n"
        "- 策略模板市场（分享 / 安装 / 评分）\n"
        "- 期权链分析与希腊字母计算\n\n"
        "## AI 智能分析（V1.5）\n"
        "- AI 智能对话助手\n"
        "- 市场情绪分析（中文金融 NLP）\n"
        "- 异常交易检测与预警\n"
        "- 策略效果归因分析\n"
        "- 自然语言查询\n\n"
        "## 平台化能力（V2.0）\n"
        "- 多租户架构与租户隔离\n"
        "- 插件系统（第三方策略接入）\n"
        "- 订阅计费系统\n"
        "- 白标解决方案\n"
        "- 开放 API 与 SDK（Python / JavaScript）"
    ),
    version="2.0.0",
    lifespan=lifespan,
    contact={"name": "OpenClaw Team", "email": "support@openclaw.com"},
    license_info={"name": "MIT"},
    openapi_tags=tags_metadata,
)

# ========== 中间件 ==========

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# 信任主机（生产环境启用）
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # 生产环境应设为具体域名列表
    )

# 限流异常处理
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )

# ========== 注册路由 ==========
app.include_router(router)
app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(backtest_router)
app.include_router(template_router)
app.include_router(options_router)
app.include_router(account_router)
app.include_router(ai_router)
app.include_router(tenant_router)
app.include_router(plugin_router)
app.include_router(billing_router)
app.include_router(open_api_router)
app.include_router(ha_router)
app.include_router(algo_router)
app.include_router(multi_market_router)
app.include_router(community_router)

# ========== Prometheus 指标 ==========
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ========== 安全响应头 ==========
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """添加安全响应头"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    # 不暴露服务端技术栈
    response.headers["X-Powered-By"] = ""
    return response


# ========== 健康检查 ==========
@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """增强健康检查 — 验证数据库和缓存连通性"""
    checks = {"status": "ok", "version": settings.app_version}

    # 数据库检查
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        checks["status"] = "degraded"

    # 缓存检查
    try:
        from .cache import get_cache
        cache = get_cache()
        checks["cache"] = "ok" if cache.ping() else "error"
    except Exception:
        checks["cache"] = "error"
        checks["status"] = "degraded"

    return checks


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
