import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .api import router

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OpenClaw量化交易API",
    description="OpenClaw决策 + FMZ执行 量化交易框架后端API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "OpenClaw量化交易后端API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host=settings.api_host, 
        port=settings.api_port, 
        reload=settings.debug
    )
