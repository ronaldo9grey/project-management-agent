import { useState, useEffect } from 'react'
import { dailyApi } from '../api'
import { Solar, HolidayUtil } from 'lunar-typescript'

interface DayInfo {
  has_report: boolean
  total_hours: number
  report_id: number
}

interface CalendarViewProps {
  onSelectDate: (date: string) => void
  onViewReport: (report: any) => void
}

export default function CalendarView({ onSelectDate, onViewReport }: CalendarViewProps) {
  const now = new Date()
  const [currentYear, setCurrentYear] = useState(now.getFullYear())
  const [currentMonth, setCurrentMonth] = useState(now.getMonth() + 1)
  const [monthData, setMonthData] = useState<Record<number, DayInfo>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [selectedDay, setSelectedDay] = useState<number | null>(null)
  
  // 月度统计
  const [monthStats, setMonthStats] = useState({
    working_days: 0,
    total_hours: 0,
    report_count: 0,
    missing_days: 0
  })
  
  // 加载月度数据
  useEffect(() => {
    loadMonthData(currentYear, currentMonth)
  }, [currentYear, currentMonth])
  
  const loadMonthData = async (year: number, month: number) => {
    setIsLoading(true)
    try {
      const result = await dailyApi.getMonthlySummary(year, month)
      setMonthData(result.days || {})
      // 解析统计信息
      setMonthStats({
        working_days: result.working_days || 0,
        total_hours: result.total_hours || 0,
        report_count: result.report_count || 0,
        missing_days: result.missing_days || 0
      })
    } catch (error) {
      console.error('加载月度数据失败:', error)
      setMonthData({})
      setMonthStats({ working_days: 0, total_hours: 0, report_count: 0, missing_days: 0 })
    } finally {
      setIsLoading(false)
    }
  }
  
  // 获取月份天数
  const getDaysInMonth = (year: number, month: number) => {
    return new Date(year, month, 0).getDate()
  }
  
  // 获取月份第一天是周几（周一开始，0=周一, 6=周日）
  const getFirstDayOfMonth = (year: number, month: number) => {
    const day = new Date(year, month - 1, 1).getDay()
    // 周日(0)转为6，其他减1
    return day === 0 ? 6 : day - 1
  }
  
  // 获取农历信息
  const getLunarInfo = (year: number, month: number, day: number) => {
    try {
      const solar = Solar.fromYmd(year, month, day)
      const lunar = solar.getLunar()
      
      // 农历日期
      const lunarDay = lunar.getDayInChinese()
      const lunarMonth = lunar.getMonthInChinese()
      
      // 节气
      const jieQi = lunar.getJieQi()
      
      // 节日
      const festivals = lunar.getFestivals()
      const solarFestivals = solar.getFestivals()
      
      // 获取节假日信息
      const holiday = HolidayUtil.getHoliday(year, month, day)
      
      // 判断是否是周末
      const weekDay = new Date(year, month - 1, day).getDay()
      const isWeekend = weekDay === 0 || weekDay === 6
      
      // 判断是否是工作日（节假日调休）
      const isWorkday = holiday ? holiday.isWork() : !isWeekend
      
      // 显示文本逻辑：
      // 1. 节气只在那一天显示（清明、立春等）
      // 2. 节假日但无节气，显示"休"
      // 3. 初一显示月份名
      // 4. 其他显示农历日
      let displayText = ''
      if (jieQi) {
        // 节气只在这一天显示
        displayText = jieQi
      } else if (holiday && !holiday.isWork()) {
        // 节假日（非工作日）显示"休"
        displayText = '休'
      } else if (lunarDay === '初一') {
        displayText = lunarMonth + '月'
      } else {
        displayText = lunarDay
      }
      
      return {
        lunarDay,
        lunarMonth,
        jieQi,
        festivals: [...festivals, ...solarFestivals],
        holiday,
        isWeekend,
        isWorkday,
        displayText
      }
    } catch (e) {
      return {
        lunarDay: '',
        lunarMonth: '',
        jieQi: null,
        festivals: [],
        holiday: null,
        isWeekend: false,
        isWorkday: true,
        displayText: ''
      }
    }
  }
  
  // 切换月份
  const changeMonth = (delta: number) => {
    let newMonth = currentMonth + delta
    let newYear = currentYear
    
    if (newMonth > 12) {
      newMonth = 1
      newYear += 1
    } else if (newMonth < 1) {
      newMonth = 12
      newYear -= 1
    }
    
    setCurrentMonth(newMonth)
    setCurrentYear(newYear)
    setSelectedDay(null)
  }
  
  // 点击日期
  const handleDayClick = async (day: number) => {
    setSelectedDay(day)
    const dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    
    // 如果有日报，获取详情
    if (monthData[day]?.has_report) {
      try {
        const result = await dailyApi.getByDate(dateStr)
        if (result.has_report) {
          onViewReport(result)
        }
      } catch (error) {
        console.error('获取日报详情失败:', error)
      }
    } else {
      onSelectDate(dateStr)
    }
  }
  
  // 生成日历格子
  const generateCalendar = () => {
    const daysInMonth = getDaysInMonth(currentYear, currentMonth)
    const firstDay = getFirstDayOfMonth(currentYear, currentMonth)
    // 周一开始的星期标题
    const weekdays = ['一', '二', '三', '四', '五', '六', '日']
    
    const cells = []
    
    // 星期标题行
    cells.push(
      <div key="header" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        gap: '2px',
        marginBottom: '8px'
      }}>
        {weekdays.map(w => (
          <div key={w} style={{
            textAlign: 'center',
            fontSize: '12px',
            fontWeight: '600',
            color: w === '六' || w === '日' ? '#ef4444' : '#64748b',
            padding: '4px'
          }}>
            {w}
          </div>
        ))}
      </div>
    )
    
    // 日期格子
    const gridCells = []
    
    // 上个月的日期填充开头空格
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear
    const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth)
    
    for (let i = 0; i < firstDay; i++) {
      const day = daysInPrevMonth - firstDay + i + 1
      const lunarInfo = getLunarInfo(prevYear, prevMonth, day)
      const isHolidayDay = lunarInfo.holiday && !lunarInfo.isWorkday
      const isWorkdayOnWeekend = lunarInfo.isWorkday && lunarInfo.isWeekend
      
      gridCells.push(
        <div key={`prev-${i}`} style={{
          aspectRatio: '1',
          background: '#f8fafc',
          borderRadius: '8px',
          border: '1px solid #f1f5f9',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: '0.4',
          padding: '2px',
          position: 'relative'
        }}>
          <span style={{
            fontSize: '18px',
            color: '#9ca3af'
          }}>
            {day}
          </span>
          <span style={{
            fontSize: '13px',
            color: '#9ca3af',
            marginTop: '2px'
          }}>
            {lunarInfo.lunarDay}
          </span>
          {/* 节假日显示"休" */}
          {isHolidayDay && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '10px',
              fontWeight: '700',
              color: '#dc2626',
              lineHeight: '1'
            }}>休</span>
          )}
          {/* 调休上班显示"班" */}
          {isWorkdayOnWeekend && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '10px',
              fontWeight: '700',
              color: '#059669',
              lineHeight: '1'
            }}>班</span>
          )}
        </div>
      )
    }
    
    // 日期格子
    const today = new Date()
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      const dayInfo = monthData[day]
      const isToday = dateStr === todayStr
      const isSelected = selectedDay === day
      const hasReport = dayInfo?.has_report
      
      // 获取农历信息
      const lunarInfo = getLunarInfo(currentYear, currentMonth, day)
      const isHoliday = lunarInfo.holiday !== null
      const isWeekendDay = lunarInfo.isWeekend && !isHoliday
      
      gridCells.push(
        <div 
          key={day}
          onClick={() => handleDayClick(day)}
          style={{
            aspectRatio: '1',
            background: isSelected 
              ? '#3b82f6' 
              : hasReport 
                ? 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)' 
                : isToday 
                  ? '#eff6ff' 
                  : isHoliday && !lunarInfo.isWorkday
                    ? '#fef2f2'
                    : '#fff',
            borderRadius: '8px',
            border: isToday 
              ? '2px solid #3b82f6' 
              : isSelected 
                ? 'none' 
                : '1px solid #e5e7eb',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s',
            position: 'relative',
            boxShadow: hasReport ? '0 2px 8px rgba(16, 185, 129, 0.15)' : 'none',
            padding: '2px'
          }}
        >
          {/* 日期数字 */}
          <span style={{
            fontSize: '18px',
            fontWeight: isToday || hasReport ? '700' : '500',
            color: isSelected ? '#fff' : 
                   isHoliday && !lunarInfo.isWorkday ? '#dc2626' :
                   isWeekendDay ? '#ef4444' :
                   hasReport ? '#059669' : isToday ? '#3b82f6' : '#1f2937'
          }}>
            {day}
          </span>
          
          {/* 农历显示 */}
          <span style={{
            fontSize: '13px',
            fontWeight: lunarInfo.jieQi ? '600' : '500',
            color: isSelected ? '#fff' :
                   lunarInfo.jieQi ? '#6366f1' :
                   isWeekendDay ? '#f87171' :
                   hasReport ? '#059669' : '#6b7280',
            marginTop: '2px',
            lineHeight: '1.2'
          }}>
            {lunarInfo.jieQi ? lunarInfo.jieQi : 
             lunarInfo.displayText === '休' ? lunarInfo.lunarDay : 
             lunarInfo.displayText}
          </span>
          
          {/* "休"字右上角醒目显示 - 节假日都显示 */}
          {lunarInfo.holiday && !lunarInfo.isWorkday && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '12px',
              fontWeight: '700',
              color: '#dc2626',
              lineHeight: '1',
              textShadow: '0 0 2px rgba(255,255,255,0.8)'
            }}>休</span>
          )}
          
          {/* "班"字右上角显示 - 调休上班 */}
          {lunarInfo.isWorkday && lunarInfo.isWeekend && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '12px',
              fontWeight: '700',
              color: '#059669',
              lineHeight: '1',
              textShadow: '0 0 2px rgba(255,255,255,0.8)'
            }}>班</span>
          )}
          
          {/* 工时显示 */}
          {hasReport && (
            <span style={{
              fontSize: '9px',
              fontWeight: '500',
              color: isSelected ? '#fff' : '#059669',
              marginTop: '1px'
            }}>
              {dayInfo.total_hours.toFixed(1)}h
            </span>
          )}
          
          {/* 有日报标记 */}
          {hasReport && !isSelected && (
            <div style={{
              position: 'absolute',
              bottom: '3px',
              left: '3px',
              width: '5px',
              height: '5px',
              background: '#10b981',
              borderRadius: '50%'
            }} />
          )}
        </div>
      )
    }
    
    // 下个月的日期填充末尾
    const nextMonth = currentMonth === 12 ? 1 : currentMonth + 1
    const nextYear = currentMonth === 12 ? currentYear + 1 : currentYear
    const remainingCells = 42 - gridCells.length // 总共42格（6行×7列）
    
    for (let i = 1; i <= remainingCells; i++) {
      const lunarInfo = getLunarInfo(nextYear, nextMonth, i)
      const isHolidayDay = lunarInfo.holiday && !lunarInfo.isWorkday
      const isWorkdayOnWeekend = lunarInfo.isWorkday && lunarInfo.isWeekend
      
      gridCells.push(
        <div key={`next-${i}`} style={{
          aspectRatio: '1',
          background: '#f8fafc',
          borderRadius: '8px',
          border: '1px solid #f1f5f9',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: '0.4',
          padding: '2px',
          position: 'relative'
        }}>
          <span style={{
            fontSize: '18px',
            color: '#9ca3af'
          }}>
            {i}
          </span>
          <span style={{
            fontSize: '13px',
            color: '#9ca3af',
            marginTop: '2px'
          }}>
            {lunarInfo.lunarDay}
          </span>
          {/* 节假日显示"休" */}
          {isHolidayDay && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '10px',
              fontWeight: '700',
              color: '#dc2626',
              lineHeight: '1'
            }}>休</span>
          )}
          {/* 调休上班显示"班" */}
          {isWorkdayOnWeekend && (
            <span style={{
              position: 'absolute',
              top: '1px',
              right: '2px',
              fontSize: '10px',
              fontWeight: '700',
              color: '#059669',
              lineHeight: '1'
            }}>班</span>
          )}
        </div>
      )
    }
    
    cells.push(
      <div key="grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        gap: '4px'
      }}>
        {gridCells}
      </div>
    )
    
    return cells
  }
  
  return (
    <div style={{
      background: 'white',
      borderRadius: '12px',
      border: '1px solid #e5e7eb',
      overflow: 'hidden'
    }}>
      {/* 月份导航 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
        borderBottom: '1px solid #e5e7eb'
      }}>
        <button
          onClick={() => changeMonth(-1)}
          style={{
            padding: '8px 12px',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          ←
        </button>
        
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>
            {currentYear} 年 {currentMonth} 月
          </div>
          {!isLoading && monthStats.working_days > 0 && (
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
              <span style={{ 
                padding: '2px 6px', 
                borderRadius: '4px',
                background: monthStats.missing_days === 0 ? '#dcfce7' : '#fef3c7',
                color: monthStats.missing_days === 0 ? '#16a34a' : '#d97706',
                fontWeight: '600'
              }}>
                {monthStats.report_count}/{monthStats.working_days}天
              </span>
              <span style={{ marginLeft: '8px' }}>{monthStats.total_hours.toFixed(1)}h</span>
              {monthStats.missing_days > 0 && (
                <span style={{ marginLeft: '8px', color: '#ef4444' }}>
                  缺{monthStats.missing_days}天
                </span>
              )}
            </div>
          )}
        </div>
        
        <button
          onClick={() => changeMonth(1)}
          style={{
            padding: '8px 12px',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          →
        </button>
      </div>
      
      {/* 图例 */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: '16px',
        padding: '8px',
        background: '#fafafa',
        borderBottom: '1px solid #e5e7eb',
        fontSize: '11px',
        color: '#64748b'
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '12px', height: '12px', background: '#d1fae5', borderRadius: '4px', border: '1px solid #a7f3d0' }}></span>
          已填报
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '12px', height: '12px', background: '#fef2f2', borderRadius: '4px', border: '1px solid #fecaca' }}></span>
          节假日
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#ef4444' }}>
          红字: 周末/节日
        </span>
      </div>
      
      {/* 日历主体 */}
      <div style={{ padding: '12px' }}>
        {isLoading ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '200px',
            color: '#64748b'
          }}>
            <span className="spinner" style={{ marginRight: '8px' }} />
            加载中...
          </div>
        ) : (
          generateCalendar()
        )}
      </div>
      
      {/* 操作提示 */}
      <div style={{
        padding: '8px 16px',
        background: '#f8fafc',
        borderTop: '1px solid #e5e7eb',
        fontSize: '12px',
        color: '#64748b',
        textAlign: 'center'
      }}>
        💡 点击绿色日期查看详情，点击空白日期填报
      </div>
    </div>
  )
}
