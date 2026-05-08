"""
置信度计算器
多维度综合计算别名匹配置信度

置信度维度：
1. 频次置信度：出现次数越多越可信
2. 时间衰减置信度：近期纠正更重要
3. 用户多样性置信度：多用户确认更可信
4. 一致性置信度：纠正结果是否一致
"""

import math
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """置信度计算器"""
    
    # 权重配置（可调整）
    WEIGHTS = {
        'frequency': 0.30,      # 频次权重
        'time_decay': 0.25,    # 时间衰减权重
        'user_diversity': 0.25,  # 用户多样性权重
        'consistency': 0.20,    # 一致性权重
    }
    
    # 阈值配置
    THRESHOLDS = {
        'min_frequency': 3,         # 最少出现次数
        'high_confidence': 0.85,    # 高置信度阈值（自动批准）
        'medium_confidence': 0.70,  # 中置信度阈值（需审核）
        'low_confidence': 0.50,     # 低置信度阈值（建议忽略）
    }
    
    def compute_frequency_confidence(self, count: int, max_count: int = 20) -> float:
        """
        计算频次置信度
        
        公式: confidence = min(1, count / max_count * 1.2)
        
        Args:
            count: 出现次数
            max_count: 最大参考次数
            
        Returns:
            频次置信度 (0-1)
        """
        if count < self.THRESHOLDS['min_frequency']:
            return 0.0
        
        # 使用sigmoid函数平滑增长
        # 3次: 0.5, 5次: 0.7, 10次: 0.9, 20次+: 1.0
        confidence = min(1.0, (count / max_count) * 1.2)
        
        return confidence
    
    def compute_decay_confidence(self, avg_weight: float) -> float:
        """
        计算时间衰减置信度
        
        Args:
            avg_weight: 平均时间衰减权重
            
        Returns:
            时间衰减置信度 (0-1)
        """
        # avg_weight已经在0-1之间，直接使用
        # 但需要考虑多次纠正的累积效果
        return avg_weight
    
    def compute_user_diversity_confidence(self, user_count: int, max_users: int = 5) -> float:
        """
        计算用户多样性置信度
        
        多用户确认表示更可信
        
        Args:
            user_count: 确认用户数
            max_users: 最大参考用户数
            
        Returns:
            用户多样性置信度 (0-1)
        """
        if user_count <= 0:
            return 0.0
        
        # 1人: 0.4, 2人: 0.6, 3人: 0.8, 5人+: 1.0
        confidence = min(1.0, 0.4 + 0.2 * (user_count - 1))
        
        return confidence
    
    def compute_consistency_confidence(self, corrections: List[Dict]) -> float:
        """
        计算一致性置信度
        
        检查同一别名是否始终纠正到同一项目
        
        Args:
            corrections: 该别名的所有纠正记录
            
        Returns:
            一致性置信度 (0-1)
        """
        if not corrections:
            return 0.0
        
        # 统计纠正到的项目分布
        project_counts = {}
        for correction in corrections:
            project_id = correction['corrected_project_id']
            project_counts[project_id] = project_counts.get(project_id, 0) + 1
        
        # 计算主要项目的占比
        total = len(corrections)
        main_project_count = max(project_counts.values())
        consistency_ratio = main_project_count / total
        
        return consistency_ratio
    
    def compute_comprehensive(
        self,
        frequency_stats: List[Dict],
        decay_stats: List[Dict],
        min_frequency: int = 3,
        min_confidence: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        综合计算置信度
        
        Args:
            frequency_stats: 频次统计数据
            decay_stats: 时间衰减统计数据
            min_frequency: 最少出现次数阈值
            min_confidence: 最低置信度阈值
            
        Returns:
            综合置信度结果
        """
        # 合并数据
        merged_data = {}
        
        # 添加频次数据
        for item in frequency_stats:
            key = (item['alias_name'], item['project_id'])
            merged_data[key] = {
                'alias_name': item['alias_name'],
                'project_id': item['project_id'],
                'project_name': item['project_name'],
                'frequency': item['count'],
                'user_count': item['user_count'],
            }
        
        # 添加时间衰减数据
        for item in decay_stats:
            key = (item['alias_name'], item['project_id'])
            if key in merged_data:
                merged_data[key]['decay_weight'] = item['avg_weight']
        
        # 计算综合置信度
        results = []
        
        for key, data in merged_data.items():
            # 过滤低频次
            if data['frequency'] < min_frequency:
                continue
            
            # 计算各维度置信度
            freq_conf = self.compute_frequency_confidence(data['frequency'])
            decay_conf = data.get('decay_weight', 0.5)
            user_conf = self.compute_user_diversity_confidence(data['user_count'])
            
            # 一致性置信度（需要原始纠正数据，暂时用简化计算）
            # 假设如果多人纠正到同一项目，一致性较高
            consistency_conf = 0.9 if data['user_count'] >= 2 else 0.7
            
            # 综合置信度
            comprehensive = (
                freq_conf * self.WEIGHTS['frequency'] +
                decay_conf * self.WEIGHTS['time_decay'] +
                user_conf * self.WEIGHTS['user_diversity'] +
                consistency_conf * self.WEIGHTS['consistency']
            )
            
            # 过滤低置信度
            if comprehensive < min_confidence:
                continue
            
            results.append({
                'alias_name': data['alias_name'],
                'project_id': data['project_id'],
                'project_name': data['project_name'],
                'frequency': data['frequency'],
                'user_count': data['user_count'],
                'confidence': round(comprehensive, 3),
                'confidence_breakdown': {
                    'frequency': round(freq_conf, 3),
                    'time_decay': round(decay_conf, 3),
                    'user_diversity': round(user_conf, 3),
                    'consistency': round(consistency_conf, 3),
                },
                'recommendation': 'auto_approve' if comprehensive >= self.THRESHOLDS['high_confidence'] else 'manual_review',
            })
        
        # 按置信度降序排序
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        logger.info(f"计算出 {len(results)} 个候选别名（置信度 >= {min_confidence})")
        
        return results
    
    def get_confidence_explanation(self, result: Dict) -> str:
        """
        获取置信度解释说明
        
        Args:
            result: 置信度计算结果
            
        Returns:
            解释文本
        """
        breakdown = result['confidence_breakdown']
        
        explanation = f"""
别名: {result['alias_name']}
项目: {result['project_name']} (ID: {result['project_id']})

置信度计算明细:
- 频次置信度: {breakdown['frequency']} (出现{result['frequency']}次)
- 时间衰减置信度: {breakdown['time_decay']} (近期权重)
- 用户多样性置信度: {breakdown['user_diversity']} ({result['user_count']}用户确认)
- 一致性置信度: {breakdown['consistency']} (纠正一致性)

综合置信度: {result['confidence']} (权重配比: 频次30%, 时间25%, 用户25%, 一致性20%)

建议: {result['recommendation']}
"""
        
        return explanation