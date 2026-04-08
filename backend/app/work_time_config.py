"""
工作时间配置模块

配置标准工作日的时间安排和计算规则
"""

# 工作时间配置（单位：小时）
WORK_TIME_CONFIG = {
    # 上午工作时间
    "morning": {
        "start": "08:15",
        "end": "12:00",
        "hours": 3.75  # 12:00 - 08:15 = 3小时45分 = 3.75小时
    },
    # 下午工作时间
    "afternoon": {
        "start": "13:45",
        "end": "18:00",
        "hours": 4.25  # 18:00 - 13:45 = 4小时15分 = 4.25小时
    },
    # 标准工作日总时长
    "total_hours_per_day": 8.0,
    
    # 午休时间（不计入工作时间）
    "lunch_break": {
        "start": "12:00",
        "end": "13:45",
        "hours": 1.75
    }
}

def get_work_hours_per_day() -> float:
    """获取标准工作日时长（小时）"""
    return WORK_TIME_CONFIG["total_hours_per_day"]

def get_morning_hours() -> float:
    """获取上午工作时长（小时）"""
    return WORK_TIME_CONFIG["morning"]["hours"]

def get_afternoon_hours() -> float:
    """获取下午工作时长（小时）"""
    return WORK_TIME_CONFIG["afternoon"]["hours"]

def calculate_work_hours(start_time: str, end_time: str) -> float:
    """
    计算两个时间点之间的工作时长（小时）
    
    参数：
    - start_time: 开始时间，格式 "HH:MM"
    - end_time: 结束时间，格式 "HH:MM"
    
    返回：工作时长（小时）
    
    注意：
    - 标准工作时间内（08:15-18:00）扣除午休
    - 加班时间（18:00之后）不扣除午休
    """
    from datetime import datetime, timedelta
    
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        
        # 计算总时长（分钟）
        total_minutes = (end - start).seconds // 60
        hours = total_minutes / 60
        
        # 定义时间点
        morning_end = datetime.strptime("12:00", "%H:%M")
        afternoon_start = datetime.strptime("13:45", "%H:%M")
        workday_end = datetime.strptime("18:00", "%H:%M")
        
        # 如果完全是加班时间（18:00之后开始），不扣除午休
        if start >= workday_end:
            return round(hours, 2)
        
        # 如果跨越午休时间，扣除午休时长
        if start < morning_end and end > afternoon_start:
            # 跨越了午休时间
            lunch_break_minutes = 105  # 1小时45分
            hours -= lunch_break_minutes / 60
        
        return round(hours, 2)
    except:
        return 0.0

def get_work_time_display() -> str:
    """
    获取工作时间显示文本
    
    返回示例："上午 08:15-12:00（3.75h）下午 13:45-18:00（4.25h）"
    """
    morning = WORK_TIME_CONFIG["morning"]
    afternoon = WORK_TIME_CONFIG["afternoon"]
    
    return (
        f"上午 {morning['start']}-{morning['end']}（{morning['hours']}h） "
        f"下午 {afternoon['start']}-{afternoon['end']}（{afternoon['hours']}h）"
    )
