from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 数据库连接池配置
_db_kwargs = {}
if "sqlite" in settings.database_url:
    _db_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # MySQL/PostgreSQL 连接池参数
    _db_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": True,  # 连接前检查可用性
    })

engine = create_engine(settings.database_url, **_db_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
