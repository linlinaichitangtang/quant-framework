"""
配置加载
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 富途 OpenD 配置
    futu_host: str = "127.0.0.1"
    futu_port: int = 11111

    # 富途交易账户配置
    futu_trd_env: str = "SIMULATE"        # SIMULATE / REAL
    futu_acc_id: str = "13285521"          # 模拟股票账户（默认）
    futu_acc_id_real: str = "281756479836523611"  # 实盘账户

    # FMZ API配置（已废弃，保留用于迁移过渡）
    fmz_api_url: str = ""
    fmz_api_key: str = ""

    # 数据源配置（已废弃，保留用于迁移过渡）
    tushare_token: Optional[str] = None

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000

    # 日志配置
    log_path: str = "storage/logs/app.log"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()