"""
数据库连接池管理模块

解决问题：
1. 避免重复创建连接池
2. 统一管理数据库连接
3. 配置合理的连接池参数
4. 应用关闭时正确释放资源
"""

import os
from typing import Generator, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from app.logger import db_logger

load_dotenv()


class DatabaseManager:
    """数据库连接池管理器（单例模式）"""
    
    _instance: Optional['DatabaseManager'] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_engine(self) -> Engine:
        """获取数据库引擎（单例）"""
        if self._engine is None:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise RuntimeError(
                    "DATABASE_URL environment variable not set.\n"
                    "Please create a .env file with DATABASE_URL or set it in environment.\n"
                    "Example: DATABASE_URL=postgresql://user:password@localhost:5432/dbname"
                )
            
            self._engine = create_engine(
                db_url,
                pool_size=10,           # 连接池大小
                max_overflow=20,        # 最大溢出连接
                pool_recycle=3600,      # 连接回收时间（1小时）
                pool_pre_ping=True,     # 连接健康检查
                echo=False,             # 不打印 SQL（生产环境）
                connect_args={
                    "connect_timeout": 5,  # 连接超时 5 秒
                }
            )
            self._session_factory = sessionmaker(bind=self._engine)
            db_logger.info("连接池已初始化: pool_size=10, max_overflow=20")
        
        return self._engine
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        if self._session_factory is None:
            self.get_engine()
        return self._session_factory()
    
    def get_connection(self) -> Connection:
        """获取数据库连接"""
        engine = self.get_engine()
        if engine is None:
            raise RuntimeError("Database engine not initialized")
        return engine.connect()
    
    @contextmanager
    def connect(self) -> Generator[Connection, None, None]:
        """上下文管理器，自动关闭连接"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    def dispose(self):
        """释放连接池资源"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            db_logger.info("连接池已释放")
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                return result is not None
        except Exception as e:
            db_logger.error(f"连接测试失败: {e}")
            return False


# 全局单例实例
db_manager = DatabaseManager()


# 便捷函数（推荐使用）
def get_engine() -> Engine:
    """获取数据库引擎"""
    return db_manager.get_engine()


def get_session() -> Session:
    """获取数据库会话"""
    return db_manager.get_session()


def get_db() -> Generator[Connection, None, None]:
    """依赖注入：获取数据库连接（FastAPI Depends）"""
    with db_manager.connect() as conn:
        yield conn


def get_db_connection() -> Connection:
    """
    直接获取数据库连接（非上下文管理器）
    
    注意：调用者需要手动关闭连接！
    推荐使用 with get_connection_context() as conn: 代替
    """
    return db_manager.get_connection()


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """上下文管理器：获取数据库连接（推荐方式）"""
    with db_manager.connect() as conn:
        yield conn


def dispose_engine():
    """释放连接池（应用关闭时调用）"""
    db_manager.dispose()


# 兼容旧代码：提供 text 导入
__all__ = [
    'db_manager',
    'get_engine',
    'get_session',
    'get_db',
    'get_db_connection',
    'get_connection',
    'dispose_engine',
    'text',
]
