"""
配置模块
集中管理所有配置项
"""
import os

class Settings:
    """系统配置"""
    # DeepSeek AI配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # Redis配置
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # 后端API
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
    
    # 上传目录
    UPLOAD_DIR = "/tmp/project-agent/uploads"
    
    # JWT配置（与现有后端一致）
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    
    # 工作时间配置
    WORK_TIME_MORNING_START = os.getenv("WORK_TIME_MORNING_START", "08:15")
    WORK_TIME_MORNING_END = os.getenv("WORK_TIME_MORNING_END", "12:00")
    WORK_TIME_AFTERNOON_START = os.getenv("WORK_TIME_AFTERNOON_START", "13:45")
    WORK_TIME_AFTERNOON_END = os.getenv("WORK_TIME_AFTERNOON_END", "18:00")
    WORK_HOURS_PER_DAY = float(os.getenv("WORK_HOURS_PER_DAY", "8.0"))

# 创建配置实例
settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
