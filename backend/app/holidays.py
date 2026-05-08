"""
中国法定节假日计算工具
"""
from datetime import date
import calendar


def get_china_holidays_2026() -> dict:
    """
    获取2026年中国法定节假日和调休工作日
    
    注意：只标记工作日上的假期，周末不重复标记
    
    返回:
    {
        'holidays': [日期列表],  # 法定节假日（落在工作日的）
        'workdays': [日期列表]   # 调休工作日（周末补班）
    }
    """
    holidays = []
    workdays = []
    
    # 元旦：1月1日-3日
    holidays.extend([
        date(2026, 1, 1),  # 周四
        date(2026, 1, 2),  # 周五
        date(2026, 1, 3),  # 周六（周末）
    ])
    
    # 春节：2月17日-23日
    holidays.extend([
        date(2026, 2, 17),  # 周二
        date(2026, 2, 18),  # 周三
        date(2026, 2, 19),  # 周四
        date(2026, 2, 20),  # 周五
        date(2026, 2, 21),  # 周六
        date(2026, 2, 22),  # 周日
        date(2026, 2, 23),  # 周一
    ])
    workdays.extend([
        date(2026, 2, 11),  # 周日补班
        date(2026, 2, 24),  # 周六补班
    ])
    
    # 清明节：4月4日-6日（无需补班）
    # 4/4周六、4/5周日本是周末，只需标记4/6周一
    holidays.append(date(2026, 4, 6))  # 周一
    
    # 广西三月三：4月17日-20日（无需补班）
    # 4/17周五、4/20周一需要休息
    # 4/18周六、4/19周日本是周末
    holidays.extend([
        date(2026, 4, 17),  # 周五
        date(2026, 4, 20),  # 周一
    ])
    # 注意：三月三无调休补班
    
    # 劳动节：5月1日-5日
    holidays.extend([
        date(2026, 5, 1),   # 周五
        date(2026, 5, 2),   # 周六（周末）
        date(2026, 5, 3),   # 周日（周末）
        date(2026, 5, 4),   # 周一
        date(2026, 5, 5),   # 周二
    ])
    workdays.extend([
        date(2026, 4, 28),  # 周日补班
        date(2026, 5, 9),   # 周六补班
    ])
    
    # 端午节：6月19日-21日
    holidays.extend([
        date(2026, 6, 19),  # 周五
        date(2026, 6, 20),  # 周六
        date(2026, 6, 21),  # 周日
    ])
    
    # 中秋节：9月11日-13日
    holidays.extend([
        date(2026, 9, 11),  # 周五
        date(2026, 9, 12),  # 周六
        date(2026, 9, 13),  # 周日
    ])
    
    # 国庆节：10月1日-7日
    holidays.extend([
        date(2026, 10, 1),  # 周四
        date(2026, 10, 2),  # 周五
        date(2026, 10, 3),  # 周六
        date(2026, 10, 4),  # 周日
        date(2026, 10, 5),  # 周一
        date(2026, 10, 6),  # 周二
        date(2026, 10, 7),  # 周三
    ])
    workdays.extend([
        date(2026, 9, 28),   # 周日补班
        date(2026, 10, 11),  # 周六补班
    ])
    
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
    all_days = set(d for d in cal.itermonthdates(year, month) if d.month == month)
    
    # 周末（周六=5，周日=6）
    weekends = set(d for d in all_days if d.weekday() >= 5)
    
    # 获取节假日数据
    if year == 2026:
        holiday_data = get_china_holidays_2026()
        holidays = set(holiday_data['holidays'])
        workdays = set(holiday_data['workdays'])
        
        # 如果不是广西，移除三月三假期
        if region != 'guangxi':
            holidays = holidays - set([date(2026, 4, 17), date(2026, 4, 20)])
    else:
        # 其他年份暂不支持，返回默认22天
        return 22
    
    # 过滤本月内的日期
    holidays_in_month = holidays & all_days
    workdays_in_month = workdays & all_days
    
    # 休息日 = (周末 | 节假日) - 调休上班
    rest_days = (weekends | holidays_in_month) - workdays_in_month
    
    # 工作日
    work_days = all_days - rest_days
    
    return len(work_days)