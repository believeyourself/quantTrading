from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# 数据库连接
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    from .models import Base
    Base.metadata.create_all(bind=engine) 