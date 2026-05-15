"""
AI调用监控与限制模块

功能：
1. 记录每次AI调用的详细信息（用户、用途、tokens、费用）
2. 统计每日调用次数，限制单用户调用上限
3. 提供管理员查询接口

安全铁律：敏感信息不上传Git
"""
import os
import asyncio
import httpx
from datetime import datetime, date
from typing import Dict, Optional
from decimal import Decimal
import logging

logger = logging.getLogger("ai_usage")

# ============== 调用限制配置 ==============
USAGE_LIMITS = {
    "daily_parse": 50,      # 日报解析：50次/用户/天
    "chat": 100,            # 智能问答：100次/用户/天
    "task_match": 100,      # 任务匹配：100次/用户/天
    "weekly_report": 10,    # 周报生成：10次/用户/天
    "knowledge_search": 50, # 知识库搜索：50次/用户/天
    "cost_import": 20,      # 成本导入：20次/用户/天
}

# DeepSeek价格（v4-flash）
PRICE_PER_TOKEN = {
    "input_cache_hit": 0.00000002,    # ¥0.02/百万tokens
    "input_cache_miss": 0.000001,     # ¥1/百万tokens
    "output": 0.000002,               # ¥2/百万tokens
}


class AIUsageTracker:
    """AI调用追踪器"""
    
    def __init__(self):
        self.db_engine = None
    
    def init_db(self, engine):
        """初始化数据库连接"""
        self.db_engine = engine
    
    async def check_limit(self, user_id: str, purpose: str) -> bool:
        """
        检查用户是否超过当日调用上限
        
        返回：True=允许调用，False=已达上限
        """
        if not self.db_engine:
            return True  # 数据库未初始化，默认允许
        
        limit = USAGE_LIMITS.get(purpose, 100)
        today = date.today()
        
        try:
            from sqlalchemy import text
            with self.db_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) as count
                    FROM ai_usage_log
                    WHERE user_id = :user_id
                      AND purpose = :purpose
                      AND DATE(request_time) = :today
                      AND success = true
                """), {"user_id": user_id, "purpose": purpose, "today": today})
                
                row = result.fetchone()
                count = row[0] if row else 0
                
                if count >= limit:
                    logger.warning(f"[AI限流] 用户 {user_id} 已达 {purpose} 上限 ({count}/{limit}次/天)")
                    return False
                
                return True
        except Exception as e:
            logger.error(f"查询调用次数失败: {e}")
            return True  # 查询失败，默认允许
    
    async def log_usage(
        self,
        user_id: str,
        username: str,
        purpose: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_hit_tokens: int = 0,
        cost_yuan: Decimal = 0,
        request_time: datetime = None,
        ip_address: str = None,
        success: bool = True,
        error_message: str = None
    ):
        """
        记录AI调用日志
        
        参数：
        - user_id: 用户ID（employee_id）
        - username: 用户姓名
        - purpose: 用途（daily_parse/chat/task_match/...）
        - model: 模型名称
        - input_tokens: 输入tokens（cache miss）
        - output_tokens: 输出tokens
        - cache_hit_tokens: 缓存命中tokens
        - cost_yuan: 费用（元）
        - request_time: 调用时间
        - ip_address: 客户端IP
        - success: 是否成功
        - error_message: 错误信息
        """
        if not self.db_engine:
            return
        
        if request_time is None:
            request_time = datetime.now()
        
        # 计算费用（如果未提供）
        if cost_yuan == 0 and (input_tokens > 0 or output_tokens > 0):
            cost_yuan = Decimal(
                cache_hit_tokens * PRICE_PER_TOKEN["input_cache_hit"] +
                input_tokens * PRICE_PER_TOKEN["input_cache_miss"] +
                output_tokens * PRICE_PER_TOKEN["output"]
            )
        
        try:
            from sqlalchemy import text
            with self.db_engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO ai_usage_log (
                        user_id, username, purpose, model,
                        input_tokens, output_tokens, cache_hit_tokens,
                        cost_yuan, request_time, ip_address,
                        success, error_message
                    ) VALUES (
                        :user_id, :username, :purpose, :model,
                        :input_tokens, :output_tokens, :cache_hit_tokens,
                        :cost_yuan, :request_time, :ip_address,
                        :success, :error_message
                    )
                """), {
                    "user_id": user_id,
                    "username": username,
                    "purpose": purpose,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_hit_tokens": cache_hit_tokens,
                    "cost_yuan": cost_yuan,
                    "request_time": request_time,
                    "ip_address": ip_address,
                    "success": success,
                    "error_message": error_message
                })
                conn.commit()
            
            logger.info(
                f"[AI调用] 用户={username}({user_id}) | "
                f"用途={purpose} | "
                f"tokens={input_tokens}/{output_tokens} | "
                f"费用={float(cost_yuan):.4f}元"
            )
        except Exception as e:
            logger.error(f"记录AI调用失败: {e}")
    
    def get_daily_stats(self, target_date: date = None) -> Dict:
        """
        获取每日统计
        
        返回：{
            "total_calls": 总调用次数,
            "total_cost": 总费用,
            "by_purpose": {用途: {calls, cost}},
            "by_user": [{user_id, username, calls, cost}]
        }
        """
        if not self.db_engine:
            return {}
        
        if target_date is None:
            target_date = date.today()
        
        try:
            from sqlalchemy import text
            with self.db_engine.connect() as conn:
                # 总统计
                total_result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_calls,
                        SUM(cost_yuan) as total_cost,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output
                    FROM ai_usage_log
                    WHERE DATE(request_time) = :date
                      AND success = true
                """), {"date": target_date})
                total_row = total_result.fetchone()
                
                # 按用途统计
                purpose_result = conn.execute(text("""
                    SELECT 
                        purpose,
                        COUNT(*) as calls,
                        SUM(cost_yuan) as cost
                    FROM ai_usage_log
                    WHERE DATE(request_time) = :date
                      AND success = true
                    GROUP BY purpose
                    ORDER BY calls DESC
                """), {"date": target_date})
                by_purpose = {}
                for row in purpose_result:
                    by_purpose[row[0]] = {
                        "calls": row[1],
                        "cost": float(row[2] or 0)
                    }
                
                # 按用户统计
                user_result = conn.execute(text("""
                    SELECT 
                        user_id,
                        username,
                        COUNT(*) as calls,
                        SUM(cost_yuan) as cost
                    FROM ai_usage_log
                    WHERE DATE(request_time) = :date
                      AND success = true
                    GROUP BY user_id, username
                    ORDER BY calls DESC
                    LIMIT 20
                """), {"date": target_date})
                by_user = []
                for row in user_result:
                    by_user.append({
                        "user_id": row[0],
                        "username": row[1],
                        "calls": row[2],
                        "cost": float(row[3] or 0)
                    })
                
                return {
                    "date": str(target_date),
                    "total_calls": total_row[0] if total_row else 0,
                    "total_cost": float(total_row[1] or 0),
                    "total_input_tokens": total_row[2] if total_row else 0,
                    "total_output_tokens": total_row[3] if total_row else 0,
                    "by_purpose": by_purpose,
                    "by_user": by_user
                }
        except Exception as e:
            logger.error(f"获取每日统计失败: {e}")
            return {}


# 全局追踪器实例
tracker = AIUsageTracker()


def init_tracker(engine):
    """初始化追踪器（在应用启动时调用）"""
    tracker.init_db(engine)
    logger.info("AI调用追踪器已初始化")


async def check_usage_limit(user_id: str, purpose: str) -> bool:
    """检查调用限制的便捷函数"""
    return await tracker.check_limit(user_id, purpose)


async def log_ai_usage(**kwargs):
    """记录调用的便捷函数"""
    await tracker.log_usage(**kwargs)


def get_ai_daily_stats(target_date: date = None) -> Dict:
    """获取每日统计的便捷函数"""
    return tracker.get_daily_stats(target_date)