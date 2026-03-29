from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "sqlite:///./quant_trade.db"
    # 生产环境请使用MySQL: "mysql+pymysql://user:password@host:port/quant_trade"
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # 数据采集配置
    ak_share_token: str = ""  # AKShare token（如需）
    tushare_token: str = ""  # Tushare token
    
    # 定时任务配置
    a_stock_collect_cron: str = "15 15 * * 1-5"  # A股收盘后15:15采集
    hk_stock_collect_cron: str = "16 16 * * 1-5"  # 港股收盘后16:16采集
    us_stock_collect_cron: str = "0 5 * * 2-6"  # 美股收盘后次日凌晨5:00采集
    
    # FMZ配置
    fmz_api_key: str = ""
    fmz_secret_key: str = ""
    fmz_cid: int = 0
    
    # 允许的CORS源
    cors_origins: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
