"""
中国法定节假日计算工具
"""
from datetime import date
import calendar
from typing import List


def get_china_holidays_2026() -> dict:
    """
    获取2026年中国法定节假日和调休工作日
    
    返回:
    {
        'holidays': [日期列表],  # 法定节假日（休息）
        'workdays': [日期列表]   # 调休工作日（周末补班）
    }
    """
    holidays = []
    workdays = []
    
    # 元旦：1月1日-3日
    holidays.extend([
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ])
    
    # 春节：2月17日-23日，调休2月11日、2月24日
    holidays.extend([
        date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19),
        date(2026, 2, 20), date(2026, 2, 21), date(2026, 2, 22), date(2026, 2, 23),
    ])
    workdays.extend([date(2026, 2, 11), date(2026, 2, 24)])
    
    # 清明节：4月4日-6日
    holidays.extend([date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6)])
    
    # 广西三月三：4月17日-18日（周四、周五，19-20日本就是周末）
    holidays.extend([date(2026, 4, 17), date(2026, 4, 18)])
    
    # 劳动节：5月1日-5日，调休4月28日、5月9日
    holidays.extend([
        date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
        date(2026, 5, 4), date(2026, 5, 5),
    ])
    workdays.extend([date(2026, 4, 28), date(2026, 5, 9)])
    
    # 端午节：6月19日-21日
    holidays.extend([date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21)])
    
    # 中秋节：9月11日-13日
    holidays.extend([date(2026, 9, 11), date(2026, 9, 12), date(2026, 9, 13)])
    
    # 国庆节：10月1日-7日，调休9月28日、10月11日
    holidays.extend([
        date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
        date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7),
    ])
    workdays.extend([date(2026, 9, 28), date(2026, 10, 11)])
    
    return {'holidays': holidays, 'workdays': workdays}


def calculate_working_days(year: int, month: int, region: str = 'guangxi') -> int:
    """
    计算指定月份的实际工作日数（考虑中国法定节假日）
    
    参数:
    - year: 年份（目前仅支持2026）
    - month: 月份
    - region: 地区（'guangxi' 包含三月三假期）
    
    返回: 工作日天数
    """
    cal = calendar.Calendar()
    
    # 所有日期
    all_days = [d for d in cal.itermonthdates(year, month) if d.month == month]
    
    # 周末（周六=5，周日=6）
    weekends = set(d for d in all_days if d.weekday() >= 5)
    
    # 获取节假日数据
    if year == 2026:
        holiday_data = get_china_holidays_2026()
        holidays = set(holiday_data['holidays'])
        workdays = set(holiday_data['workdays'])
        
        # 如果不是广西，移除三月三假期
        if region != 'guangxi':
            holidays = holidays - set([date(2026, 4, 17), date(2026, 4, 18)])
    else:
        # 其他年份暂不支持，返回默认22天
        return 22
    
    # 过滤本月内的日期
    holidays_in_month = holidays & set(all_days)
    workdays_in_month = workdays & set(all_days)
    
    # 休息日 = 周末 + 节假日 - 调休工作日
    rest_days = weekends | holidays_in_month - workdays_in_month
    
    # 工作日
    work_days = [d for d in all_days if d not in rest_days]
    
    return len(work_days)
