from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # ========== 应用配置 ==========
    app_name: str = "OpenClaw"
    app_version: str = "2.0.0"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"  # DEBUG / INFO / WARNING / ERROR
    workers: int = 1  # Uvicorn worker 数量

    # ========== 安全配置 ==========
    secret_key: str = "openclaw_quant_secret_key_change_in_production_2024"  # 生产环境必须通过环境变量覆盖
    access_token_expire_minutes: int = 60 * 24  # 24 小时
    refresh_token_expire_days: int = 30
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]  # 生产环境应通过环境变量 CORS_ORIGINS 覆盖为具体域名
    allowed_hosts: List[str] = ["*"]  # 生产环境应设为具体域名列表

    # ========== 数据库配置 ==========
    database_url: str = "sqlite:///./quant_trade.db"
    # 生产环境: "mysql+pymysql://user:password@host:port/quant_trade"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    # ========== Redis 配置 ==========
    redis_url: Optional[str] = None  # "redis://localhost:6379/0"，为空则使用内存缓存

    # ========== API 限流 ==========
    rate_limit: str = "60/minute"  # 默认限流规则
    rate_limit_login: str = "5/minute"  # 登录接口限流

    # ========== 数据采集配置 ==========
    ak_share_token: str = ""
    tushare_token: str = ""
    a_stock_collect_cron: str = "15 15 * * 1-5"
    hk_stock_collect_cron: str = "16 16 * * 1-5"
    us_stock_collect_cron: str = "0 5 * * 2-6"

    # ========== FMZ 配置 ==========
    fmz_api_key: str = ""
    fmz_secret_key: str = ""
    fmz_cid: int = 0

    # ========== 通知配置 ==========
    wechat_webhook_url: Optional[str] = None
    dingtalk_webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None

    # ========== AI/LLM 配置 ==========
    llm_provider: str = "openai"  # openai / deepseek / ollama
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"  # OpenAI 兼容 API 地址
    llm_model: str = "gpt-4o-mini"  # 模型名称
    llm_max_tokens: int = 2000
    llm_temperature: float = 0.7

    # ========== 多租户配置 ==========
    multi_tenant_enabled: bool = False  # 是否启用多租户模式
    default_tenant_id: str = "default"  # 默认租户ID
    tenant_header: str = "X-Tenant-ID"  # 租户识别请求头

    # ========== 计费配置 ==========
    billing_enabled: bool = False
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    trial_days: int = 14

    # ========== 多市场配置 ==========
    crypto_exchange_api: str = ""  # 加密货币交易所 API
    crypto_api_key: str = ""
    crypto_api_secret: str = ""
    futures_data_source: str = "simulation"  # simulation/live
    global_timezone: str = "Asia/Shanghai"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
