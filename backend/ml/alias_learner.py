"""
项目别名学习器
负责提取纠正数据、统计分析
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/project-agent/backend')

from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.database import get_connection
import logging

logger = logging.getLogger(__name__)


class AliasLearner:
    """项目别名学习器"""
    
    def extract_corrections(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        提取用户纠正记录
        
        Args:
            days: 提取最近几天的数据
            
        Returns:
            纠正记录列表
        """
        with get_connection() as conn:
            result = conn.execute("""
                SELECT 
                    pc.id,
                    pc.user_id,
                    pc.original_hint,
                    pc.original_match,
                    pc.corrected_project_id,
                    p.name as corrected_project_name,
                    pc.confidence_before,
                    pc.created_at,
                    EXTRACT(DAY FROM NOW() - pc.created_at) as days_ago
                FROM project_corrections pc
                JOIN projects p ON p.id = pc.corrected_project_id
                WHERE pc.created_at >= NOW() - INTERVAL '%s days'
                ORDER BY pc.original_hint, pc.created_at DESC
            """, (days,))
            
            corrections = [dict(row) for row in result]
        
        logger.info(f"提取到 {len(corrections)} 条纠正记录（最近{days}天）")
        return corrections
    
    def calculate_frequency(self, corrections: List[Dict]) -> List[Dict[str, Any]]:
        """
        计算别名出现频次
        
        Args:
            corrections: 纠正记录列表
            
        Returns:
            频次统计数据
        """
        # 按别名分组统计
        frequency_map = {}
        
        for correction in corrections:
            key = (correction['original_hint'], correction['corrected_project_id'])
            
            if key not in frequency_map:
                frequency_map[key] = {
                    'alias_name': correction['original_hint'],
                    'project_id': correction['corrected_project_id'],
                    'project_name': correction['corrected_project_name'],
                    'count': 0,
                    'users': set(),
                    'first_seen': correction['created_at'],
                    'last_seen': correction['created_at'],
                }
            
            frequency_map[key]['count'] += 1
            frequency_map[key]['users'].add(correction['user_id'])
            
            # 更新时间范围
            if correction['created_at'] < frequency_map[key]['first_seen']:
                frequency_map[key]['first_seen'] = correction['created_at']
            if correction['created_at'] > frequency_map[key]['last_seen']:
                frequency_map[key]['last_seen'] = correction['created_at']
        
        # 转为列表并计算用户数
        results = []
        for item in frequency_map.values():
            item['user_count'] = len(item['users'])
            item['users'] = list(item['users'])  # 转为列表以便序列化
            results.append(item)
        
        # 按频次降序排序
        results.sort(key=lambda x: x['count'], reverse=True)
        
        logger.info(f"统计到 {len(results)} 个候选别名")
        return results
    
    def calculate_time_decay(self, corrections: List[Dict]) -> List[Dict[str, Any]]:
        """
        计算时间衰减权重
        
        时间衰减公式: weight = e^(-days_ago / half_life)
        
        Args:
            corrections: 纠正记录列表
            
        Returns:
            时间衰减统计数据
        """
        import math
        
        # 半衰期：30天（30天前的数据权重减半）
        half_life = 30
        
        decay_map = {}
        
        for correction in corrections:
            key = (correction['original_hint'], correction['corrected_project_id'])
            days_ago = correction.get('days_ago', 0)
            
            # 计算衰减权重
            decay_weight = math.exp(-days_ago / half_life)
            
            if key not in decay_map:
                decay_map[key] = {
                    'alias_name': correction['original_hint'],
                    'project_id': correction['corrected_project_id'],
                    'project_name': correction['corrected_project_name'],
                    'total_weight': 0,
                    'weight_count': 0,
                    'avg_weight': 0,
                }
            
            decay_map[key]['total_weight'] += decay_weight
            decay_map[key]['weight_count'] += 1
        
        # 计算平均权重
        results = []
        for item in decay_map.values():
            item['avg_weight'] = item['total_weight'] / item['weight_count']
            results.append(item)
        
        # 按平均权重降序排序
        results.sort(key=lambda x: x['avg_weight'], reverse=True)
        
        return results
    
    def cleanup_old_corrections(self, days: int = 30) -> int:
        """
        清理过期的纠正记录
        
        Args:
            days: 删除多少天前的数据
            
        Returns:
            删除的记录数
        """
        with get_connection() as conn:
            result = conn.execute("""
                DELETE FROM project_corrections
                WHERE created_at < NOW() - INTERVAL '%s days'
                RETURNING id
            """, (days,))
            
            deleted = len(list(result))
            conn.commit()
        
        return deleted
