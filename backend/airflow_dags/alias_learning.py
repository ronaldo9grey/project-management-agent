"""
项目别名自动学习DAG
执行频率：每日凌晨2点
功能：
  1. 提取用户纠正记录
  2. 统计分析别名模式
  3. 计算置信度
  4. 更新知识库
  5. 生成提示词更新通知
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import logging

# 导入学习模块
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/project-agent/backend')
from ml.alias_learner import AliasLearner
from ml.confidence_calculator import ConfidenceCalculator
from ml.knowledge_base_updater import KnowledgeBaseUpdater

logger = logging.getLogger(__name__)

# 默认参数
default_args = {
    'owner': 'project-agent',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# 创建DAG
with DAG(
    'project_alias_learning',
    default_args=default_args,
    description='项目别名自动学习系统',
    schedule_interval='0 2 * * *',  # 每天凌晨2点
    start_date=datetime(2026, 5, 1),
    catchup=False,
    tags=['ml', 'alias', 'learning'],
) as dag:

    # Task 1: 提取纠正数据
    def extract_corrections(**context):
        """提取过去7天的用户纠正记录"""
        learner = AliasLearner()
        corrections = learner.extract_corrections(days=7)
        
        logger.info(f"提取到 {len(corrections)} 条纠正记录")
        
        # 推送到XCom供后续任务使用
        context['ti'].xcom_push(key='corrections', value=corrections)
        
        return corrections

    extract_task = PythonOperator(
        task_id='extract_corrections',
        python_callable=extract_corrections,
    )

    # Task Group: 统计分析
    with TaskGroup('statistical_analysis') as analysis_group:
        
        def calculate_frequency(**context):
            """计算别名出现频次"""
            ti = context['ti']
            corrections = ti.xcom_pull(task_ids='extract_corrections', key='corrections')
            
            learner = AliasLearner()
            frequency_stats = learner.calculate_frequency(corrections)
            
            logger.info(f"统计到 {len(frequency_stats)} 个候选别名")
            
            ti.xcom_push(key='frequency_stats', value=frequency_stats)
            return frequency_stats

        frequency_task = PythonOperator(
            task_id='calculate_frequency',
            python_callable=calculate_frequency,
        )

        def calculate_time_decay(**context):
            """计算时间衰减权重"""
            ti = context['ti']
            corrections = ti.xcom_pull(task_ids='extract_corrections', key='corrections')
            
            learner = AliasLearner()
            decay_stats = learner.calculate_time_decay(corrections)
            
            ti.xcom_push(key='decay_stats', value=decay_stats)
            return decay_stats

        decay_task = PythonOperator(
            task_id='calculate_time_decay',
            python_callable=calculate_time_decay,
        )

        frequency_task >> decay_task

    # Task 3: 计算置信度
    def compute_confidence(**context):
        """综合计算置信度"""
        ti = context['ti']
        
        # 获取统计数据
        frequency_stats = ti.xcom_pull(task_ids='statistical_analysis.calculate_frequency', key='frequency_stats')
        decay_stats = ti.xcom_pull(task_ids='statistical_analysis.calculate_time_decay', key='decay_stats')
        
        # 计算综合置信度
        calculator = ConfidenceCalculator()
        confidence_results = calculator.compute_comprehensive(
            frequency_stats=frequency_stats,
            decay_stats=decay_stats,
            min_frequency=3,        # 最少出现3次
            min_confidence=0.7,     # 最低置信度0.7
        )
        
        # 分类
        high_confidence = [r for r in confidence_results if r['confidence'] >= 0.85]
        medium_confidence = [r for r in confidence_results if 0.7 <= r['confidence'] < 0.85]
        
        logger.info(f"高置信度: {len(high_confidence)}, 中置信度: {len(medium_confidence)}")
        
        ti.xcom_push(key='high_confidence', value=high_confidence)
        ti.xcom_push(key='medium_confidence', value=medium_confidence)
        ti.xcom_push(key='all_results', value=confidence_results)
        
        return confidence_results

    confidence_task = PythonOperator(
        task_id='compute_confidence',
        python_callable=compute_confidence,
    )

    # Task 4: 更新知识库
    def update_knowledge_base(**context):
        """更新别名知识库"""
        ti = context['ti']
        
        # 获取高置信度结果
        high_confidence = ti.xcom_pull(task_ids='compute_confidence', key='high_confidence')
        
        if not high_confidence:
            logger.info("没有需要自动更新的别名")
            return
        
        # 更新知识库
        updater = KnowledgeBaseUpdater()
        update_results = updater.batch_update(
            aliases=high_confidence,
            source='auto_learning',
            auto_approve=True,  # 高置信度自动批准
        )
        
        logger.info(f"成功更新 {len(update_results['success'])} 条别名")
        
        # 记录失败情况
        if update_results['failed']:
            logger.warning(f"更新失败 {len(update_results['failed'])} 条")
        
        ti.xcom_push(key='update_results', value=update_results)
        return update_results

    update_task = PythonOperator(
        task_id='update_knowledge_base',
        python_callable=update_knowledge_base,
    )

    # Task 5: 生成提示词更新通知
    def notify_prompt_update(**context):
        """通知系统更新提示词"""
        ti = context['ti']
        update_results = ti.xcom_pull(task_ids='update_knowledge_base', key='update_results')
        
        if not update_results or not update_results.get('success'):
            logger.info("无新别名，跳过提示词更新")
            return
        
        # 写入更新标记文件
        flag_file = '/tmp/alias_prompt_need_update.flag'
        with open(flag_file, 'w') as f:
            f.write(f"{datetime.now().isoformat()}\n")
            f.write(f"new_aliases: {len(update_results['success'])}\n")
        
        logger.info(f"已创建提示词更新标记文件: {flag_file}")
        
        return True

    notify_task = PythonOperator(
        task_id='notify_prompt_update',
        python_callable=notify_prompt_update,
    )

    # Task 6: 清理过期数据
    def cleanup_old_data(**context):
        """清理30天前的纠正记录"""
        learner = AliasLearner()
        deleted = learner.cleanup_old_corrections(days=30)
        
        logger.info(f"已清理 {deleted} 条过期记录")
        return deleted

    cleanup_task = PythonOperator(
        task_id='cleanup_old_data',
        python_callable=cleanup_old_data,
    )

    # 设置任务依赖
    extract_task >> analysis_group >> confidence_task >> update_task >> notify_task >> cleanup_task
