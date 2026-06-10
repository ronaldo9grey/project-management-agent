// 人员项目投入分析卡片
function PersonAnalysisCard() {
  const currentYear = new Date().getFullYear()
  const [selectedEmployee, setSelectedEmployee] = useState<string>('')
  const [selectedYear, setSelectedYear] = useState<number>(currentYear)
  const [allEmployees, setAllEmployees] = useState<string[]>([])
  const [data, setData] = useState<{
    employee_name: string
    year: number
    total_hours: number
    project_count: number
    projects: Array<{ project_name: string; hours: number; percent: number; report_count: number }>
    monthly_trend: Array<{ month: number; hours: number }>
  } | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    apiClient.get('/api/agent/stats/person-project-analysis', {
      params: { employee_name: 'admin', year: currentYear }
    }).then(res => {
      setAllEmployees(res.data.all_employees || [])
      if (res.data.all_employees && res.data.all_employees.length > 0) {
        setSelectedEmployee(res.data.all_employees[0])
      }
    }).catch(err => console.error('获取员工列表失败:', err))
  }, [])

  useEffect(() => {
    if (!selectedEmployee) return
    setIsLoading(true)
    apiClient.get('/api/agent/stats/person-project-analysis', {
      params: { employee_name: selectedEmployee, year: selectedYear }
    }).then(res => {
      setData(res.data)
      setIsLoading(false)
    }).catch(err => {
      console.error('获取人员分析失败:', err)
      setIsLoading(false)
    })
  }, [selectedEmployee, selectedYear])

  if (isLoading || !data) {
    return (
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>👤 人员项目投入分析</h3>
        </div>
        <div className="card-body"><div className="skeleton skeleton-box" style={{ height: '400px' }} /></div>
      </div>
    )
  }

  const topProjects = data.projects.slice(0, 6)
  const otherHours = data.projects.slice(6).reduce((sum, p) => sum + p.hours, 0)
  if (otherHours > 0) topProjects.push({ project_name: '其他项目', hours: otherHours, percent: 0, report_count: 0 })
  
  const totalPieHours = topProjects.reduce((sum, p) => sum + p.hours, 0)
  topProjects.forEach(p => { p.percent = totalPieHours > 0 ? Math.round(p.hours / totalPieHours * 100) : 0 })
  
  const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#94a3b8']
  const monthCount = data.monthly_trend?.length || 1
  const chartWidth = Math.max(400, monthCount * 60)
  
  return (
    <div className="card" style={{ marginBottom: '20px' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>👤 人员项目投入分析</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: 'white', fontSize: '14px' }}>
            {allEmployees.map(emp => (<option key={emp} value={emp}>{emp}</option>))}
          </select>
          <select value={selectedYear} onChange={(e) => setSelectedYear(parseInt(e.target.value))} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: 'white', fontSize: '14px' }}>
            <option value={currentYear - 1}>{currentYear - 1}年</option>
            <option value={currentYear}>{currentYear}年</option>
          </select>
        </div>
      </div>
      <div className="card-body" style={{ padding: '24px' }}>
        <div style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)', borderRadius: '12px', padding: '16px 20px', marginBottom: '24px', display: 'flex', gap: '40px', alignItems: 'center' }}>
          <div><span style={{ fontSize: '14px', color: '#64748b' }}>总工时（正式项目）</span><div style={{ fontSize: '32px', fontWeight: '700', color: '#1e40af' }}>{data.total_hours}h</div></div>
          <div style={{ width: '1px', height: '40px', background: '#cbd5e1' }} />
          <div><span style={{ fontSize: '14px', color: '#64748b' }}>参与正式项目</span><div style={{ fontSize: '32px', fontWeight: '700', color: '#059669' }}>{data.project_count}个</div></div>
        </div>

        {data.projects.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', color: '#1e40af' }}>📋 正式项目工时详情</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
              {data.projects.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '14px 16px', background: i % 2 === 0 ? '#eff6ff' : '#f8fafc', borderRadius: '10px', border: '1px solid #dbeafe' }}>
                  <div style={{ width: '16px', height: '16px', borderRadius: '50%', background: colors[i % 7], marginRight: '12px', flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: '14px', fontWeight: '500', color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.project_name}</div></div>
                  <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '12px' }}><span style={{ fontWeight: '700', color: '#1e40af', fontSize: '16px' }}>{p.hours}h</span><span style={{ fontSize: '13px', color: '#64748b', marginLeft: '8px' }}>{p.percent}%</span></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '32px' }}>
          <div>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px', color: '#374151' }}>📊 工时占比</h4>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <svg width="240" height="240" viewBox="0 0 240 240">
                {(() => {
                  const radius = 100, cx = 120, cy = 120
                  let startAngle = 0
                  return topProjects.map((p, i) => {
                    const angle = (p.percent / 100) * 360, endAngle = startAngle + angle
                    const x1 = cx + radius * Math.cos((startAngle - 90) * Math.PI / 180)
                    const y1 = cy + radius * Math.sin((startAngle - 90) * Math.PI / 180)
                    const x2 = cx + radius * Math.cos((endAngle - 90) * Math.PI / 180)
                    const y2 = cy + radius * Math.sin((endAngle - 90) * Math.PI / 180)
                    const largeArc = angle > 180 ? 1 : 0
                    const path = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`
                    const midAngle = (startAngle + endAngle) / 2 - 90
                    const labelRadius = radius * 0.65
                    const lx = cx + labelRadius * Math.cos(midAngle * Math.PI / 180)
                    const ly = cy + labelRadius * Math.sin(midAngle * Math.PI / 180)
                    startAngle = endAngle
                    return (
                      <g key={i}>
                        <path d={path} fill={colors[i] || '#94a3b8'} stroke="white" strokeWidth="3" />
                        {p.percent >= 6 && (<text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" style={{ fontSize: '14px', fontWeight: '700', fill: 'white' }}>{p.percent}%</text>)}
                      </g>
                    )
                  })
                })()}
              </svg>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '12px', justifyContent: 'center' }}>
                {topProjects.slice(0, 5).map((p, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: colors[i] }} />
                    <span style={{ color: '#475569' }}>{(p.project_name || '其他').substring(0, 8)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px', color: '#374151' }}>📈 月度工时趋势</h4>
            <div style={{ overflowX: 'auto' }}>
              <svg width={chartWidth} height="200" viewBox={`0 0 ${chartWidth} 200`} style={{ background: '#f8fafc', borderRadius: '12px', minWidth: '100%' }}>
                {(() => {
                  const months = data.monthly_trend
                  if (!months || months.length === 0) return null
                  const maxHours = Math.max(...months.map(m => m.hours), 1)
                  const padding = { left: 45, right: 20, top: 35, bottom: 35 }
                  const chartWidthInner = chartWidth - padding.left - padding.right
                  const chartHeight = 200 - padding.top - padding.bottom
                  const xStep = chartWidthInner / Math.max(months.length - 1, 1)
                  const points = months.map((m, i) => {
                    const x = padding.left + i * xStep
                    const y = padding.top + chartHeight - (m.hours / maxHours) * chartHeight
                    return `${x},${y}`
                  }).join(' ')
                  const areaPoints = `${padding.left},${padding.top + chartHeight} ${points} ${padding.left + (months.length - 1) * xStep},${padding.top + chartHeight}`
                  return (
                    <>
                      {[0, 50, 100].map(pct => {
                        const y = padding.top + chartHeight - (pct / 100) * chartHeight
                        return <line key={pct} x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" />
                      })}
                      <polygon points={areaPoints} fill="url(#gradPerson)" opacity="0.3" />
                      <defs><linearGradient id="gradPerson" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stopColor="#3b82f6" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></linearGradient></defs>
                      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                      {months.map((m, i) => {
                        const x = padding.left + i * xStep
                        const y = padding.top + chartHeight - (m.hours / maxHours) * chartHeight
                        return (
                          <g key={i}>
                            <circle cx={x} cy={y} r="6" fill="#3b82f6" stroke="white" strokeWidth="3" />
                            <text x={x} y={y - 14} textAnchor="middle" style={{ fontSize: '13px', fontWeight: '700', fill: '#1e40af' }}>{m.hours}h</text>
                            <text x={x} y={padding.top + chartHeight + 20} textAnchor="middle" style={{ fontSize: '13px', fill: '#64748b', fontWeight: '500' }}>{m.month}月</text>
                          </g>
                        )
                      })}
                    </>
                  )
                })()}
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

