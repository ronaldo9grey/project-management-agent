"""
知识库更新器
负责将学习到的别名更新到知识库

更新策略：
1. 高置信度(>=0.85): 自动批准
2. 中置信度(0.7-0.85): 需人工审核
3. 已存在别名: 更新使用统计
"""

from typing import List, Dict, Any
from app.database import get_connection
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseUpdater:
    """知识库更新器"""
    
    def batch_update(
        self,
        aliases: List[Dict[str, Any]],
        source: str = 'auto_learning',
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        """
        批量更新别名知识库
        
        Args:
            aliases: 别名列表（含置信度）
            source: 数据来源
            auto_approve: 是否自动批准
            
        Returns:
            更新结果统计
        """
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'updated': [],
        }
        
        with get_connection() as conn:
            for alias in aliases:
                try:
                    # 检查是否已存在
                    existing = conn.execute("""
                        SELECT id, confidence, usage_count, is_active
                        FROM project_alias
                        WHERE alias_name = %s
                    """, (alias['alias_name'],)).fetchone()
                    
                    if existing:
                        # 已存在，更新使用统计
                        conn.execute("""
                            UPDATE project_alias
                            SET usage_count = usage_count + %s,
                                last_used_at = NOW(),
                                confidence = GREATEST(confidence, %s)
                            WHERE id = %s
                        """, (alias['frequency'], alias['confidence'], existing[0]))
                        
                        results['updated'].append({
                            'alias_name': alias['alias_name'],
                            'old_confidence': existing[1],
                            'new_confidence': alias['confidence'],
                        })
                        
                        logger.info(f"更新已存在别名: {alias['alias_name']}")
                        continue
                    
                    # 插入新别名
                    is_active = auto_approve and alias.get('recommendation') == 'auto_approve'
                    
                    conn.execute("""
                        INSERT INTO project_alias
                        (alias_name, project_id, source, confidence, usage_count, is_active, created_at, last_used_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, (
                        alias['alias_name'],
                        alias['project_id'],
                        source,
                        alias['confidence'],
                        alias['frequency'],
                        is_active,
                    ))
                    
                    results['success'].append(alias)
                    logger.info(f"插入新别名: {alias['alias_name']} -> {alias['project_name']}")
                    
                except Exception as e:
                    logger.error(f"更新别名失败: {alias['alias_name']}, 错误: {e}")
                    results['failed'].append({
                        'alias_name': alias['alias_name'],
                        'error': str(e),
                    })
            
            conn.commit()
        
        logger.info(f"""
知识库更新完成:
- 成功插入: {len(results['success'])}
- 已存在更新: {len(results['updated'])}
- 失败: {len(results['failed'])}
""")
        
        return results
    
    def get_pending_aliases(self) -> List[Dict[str, Any]]:
        """
        获取待审核的别名
        
        Returns:
            待审核别名列表
        """
        with get_connection() as conn:
            result = conn.execute("""
                SELECT 
                    pa.id,
                    pa.alias_name,
                    pa.project_id,
                    p.name as project_name,
                    pa.confidence,
                    pa.usage_count,
                    pa.source,
                    pa.created_at
                FROM project_alias pa
                JOIN projects p ON p.id = pa.project_id
                WHERE pa.is_active = FALSE
                AND pa.confidence >= 0.7
                ORDER BY pa.confidence DESC, pa.usage_count DESC
            """)
            
            return [dict(row) for row in result]
    
    def approve_alias(self, alias_id: int) -> bool:
        """
        批准别名
        
        Args:
            alias_id: 别名ID
            
        Returns:
            是否成功
        """
        with get_connection() as conn:
            conn.execute("""
                UPDATE project_alias
                SET is_active = TRUE
                WHERE id = %s
            """, (alias_id,))
            
            conn.commit()
        
        logger.info(f"批准别名ID: {alias_id}")
        return True
    
    def reject_alias(self, alias_id: int) -> bool:
        """
        拒绝别名
        
        Args:
            alias_id: 别名ID
            
        Returns:
            是否成功
        """
        with get_connection() as conn:
            conn.execute("""
                DELETE FROM project_alias
                WHERE id = %s
            """, (alias_id,))
            
            conn.commit()
        
        logger.info(f"拒绝并删除别名ID: {alias_id}")
        return True
    
    def get_active_aliases_for_prompt(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取活跃别名用于生成提示词
        
        Args:
            limit: 最大数量
            
        Returns:
            别名列表
        """
        with get_connection() as conn:
            result = conn.execute("""
                SELECT 
                    pa.alias_name,
                    pa.project_id,
                    p.name as project_name,
                    pa.confidence,
                    pa.usage_count
                FROM project_alias pa
                JOIN projects p ON p.id = pa.project_id
                WHERE pa.is_active = TRUE
                AND (pa.confidence >= 0.8 OR pa.source = 'manual')
                ORDER BY pa.usage_count DESC, pa.confidence DESC
                LIMIT %s
            """, (limit,))
            
            return [dict(row) for row in result]
    
    def export_aliases_to_markdown(self) -> str:
        """
        导出别名为Markdown格式（用于提示词）
        
        Returns:
            Markdown文本
        """
        aliases = self.get_active_aliases_for_prompt()
        
        if not aliases:
            return ""
        
        markdown = "| 用户常用别名 | 项目ID | 正式项目名 |\n"
        markdown += "|------------|-------|-----------|\n"
        
        for alias in aliases:
            markdown += f"| {alias['alias_name']} | {alias['project_id']} | {alias['project_name']} |\n"
        
        return markdown
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取知识库统计
        
        Returns:
            统计数据
        """
        with get_connection() as conn:
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_active THEN 1 END) as active,
                    COUNT(CASE WHEN NOT is_active THEN 1 END) as pending,
                    AVG(confidence) as avg_confidence,
                    MAX(usage_count) as max_usage,
                    SUM(usage_count) as total_usage
                FROM project_alias
            """).fetchone()
            
            return dict(stats) if stats else {}