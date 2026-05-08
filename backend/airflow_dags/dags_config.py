"""
Airflow DAG配置
"""

# 数据库连接
DB_CONNECTION = {
    'host': 'localhost',
    'port': 5432,
    'database': 'project_cost_tracking',
    'user': 'yjydb',
    'password': 'qv52A03xcxAQCoDglUJelm4Sb',
}

# 学习参数
LEARNING_CONFIG = {
    # 数据提取
    'extraction_days': 7,           # 提取最近7天数据
    
    # 置信度阈值
    'min_frequency': 3,             # 最少出现3次才考虑
    'min_confidence': 0.70,         # 最低置信度0.7
    'high_confidence': 0.85,        # 高置信度0.85（自动批准）
    
    # 权重配置
    'weights': {
        'frequency': 0.30,
        'time_decay': 0.25,
        'user_diversity': 0.25,
        'consistency': 0.20,
    },
    
    # 时间衰减
    'time_decay_half_life': 30,     # 半衰期30天
    
    # 清理
    'cleanup_days': 30,             # 清理30天前的数据
}

# 提示词生成
PROMPT_CONFIG = {
    'max_aliases': 50,              # 提示词最多包含50个别名
    'min_confidence': 0.8,          # 只包含置信度>=0.8的别名
}

# 监控配置
MONITOR_CONFIG = {
    'alert_email': 'admin@example.com',
    'log_level': 'INFO',
}