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

    logger.info(f"{settings.app_name} v{settings.app_version} 启动完成 (debug={settings.debug})")

    yield

    # 关闭
    from .cache import get_cache
    get_cache().close()
    logger.info("应用已关闭")


# ========== 创建 FastAPI 应用 ==========
app = FastAPI(
    title="OpenClaw量化交易API",
    description="OpenClaw决策 + FMZ执行 量化交易框架后端API",
    version="1.0.0",
    lifespan=lifespan,
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
