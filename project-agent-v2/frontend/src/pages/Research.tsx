/**
 * 研发项目工时归集 - 项目维度展示
 */

import { useState, useEffect } from 'react';
import { apiClient } from '../api';
import { confirm } from '../components/ConfirmDialog';
import SharedHeader from '../components/SharedHeader';

interface ProjectSummary {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  budget_2026: number;
  workdays: number[];
  days_in_month?: number;
  members: Record<string, {
    is_manager: boolean;
    employment_end: string | null;
    monthly_hours: Record<number, number>;
    daily_hours: Record<number, number>;
    total_hours: number;
  }>;
  monthly_total: Record<number, number>;
  daily_total?: Record<number, number>;
  monthly_total_sum?: number;
  annual_total: number;
}

export default function Research() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [workdays, setWorkdays] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedYear, setSelectedYear] = useState(2026);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [isAllocated, setIsAllocated] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const url = selectedMonth 
        ? `/api/agent/research/allocations/project-summary?year=${selectedYear}&month=${selectedMonth}`
        : `/api/agent/research/allocations/project-summary?year=${selectedYear}`;
      const res = await apiClient.get(url);
      setProjects(res.data.projects || []);
      setWorkdays(res.data.workdays || []);
      setIsAllocated(res.data.projects && res.data.projects.length > 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [selectedYear, selectedMonth]);

  const handleAllocateAll = async () => {
    const ok = await confirm({
      title: '确认归集所有项目工时？',
      message: '归集后将排除周末和节假日，按项目预算比例分配。',
      type: 'warning'
    });
    if (!ok) return;

    try {
      const res = await apiClient.post('/api/agent/research/allocate-all');
      alert(`归集完成！共${res.data.total_records}条记录`);
      loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || '归集失败');
    }
  };

  const handleExport = async () => {
    const ok = await confirm({
      title: '导出工时表？',
      message: selectedMonth 
        ? `将导出${selectedYear}年${selectedMonth}月的工时数据`
        : `将导出${selectedYear}年全年的工时数据`,
      type: 'info'
    });
    if (!ok) return;

    try {
      const url = selectedMonth
        ? `/api/agent/research/allocations/export?year=${selectedYear}&month=${selectedMonth}`
        : `/api/agent/research/allocations/export?year=${selectedYear}`;
      const res = await apiClient.get(url);
      
      // 处理base64 Excel数据
      const excelData = res.data.excel_data;
      const byteCharacters = atob(excelData);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = res.data.filename;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      setError(err.response?.data?.detail || '导出失败');
    }
  };

  const monthNames = ['一月', '二月', '三月', '四月', '五月', '六月', 
                      '七月', '八月', '九月', '十月', '十一月', '十二月'];

  // 计算工期天数
  const calcDays = (start: string, end: string) => {
    const s = new Date(start);
    const e = new Date(end);
    return Math.max(0, Math.ceil((e.getTime() - s.getTime()) / (1000 * 60 * 60 * 24)));
  };

  return (
    <div className="page-container">
      <SharedHeader activePath="/research" />

      <main className="content-wrapper">
        {/* 页面标题 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#111827' }}>研发项目工时归集</h1>
            <p style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>
              按项目维度展示人员投入（已排除周末和节假日）
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            {!isAllocated && (
              <button onClick={handleAllocateAll} className="btn-primary">⚡ 一键归集</button>
            )}
            <button onClick={handleExport} className="btn-outline">📥 导出Excel</button>
          </div>
        </div>

        {error && (
          <div className="alert-error">
            {error}
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        {/* 筛选 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <select 
            value={selectedYear} 
            onChange={e => setSelectedYear(parseInt(e.target.value))}
            className="select-input"
          >
            <option value={2026}>2026年</option>
          </select>
          <select 
            value={selectedMonth || ''} 
            onChange={e => setSelectedMonth(e.target.value ? parseInt(e.target.value) : null)}
            className="select-input"
          >
            <option value="">全年</option>
            {monthNames.map((name, i) => (
              <option key={i} value={i + 1}>{name}</option>
            ))}
          </select>
          {projects.length > 0 && (
            <span style={{ color: '#6b7280', fontSize: '14px' }}>
              {selectedMonth ? `${workdays.length}个工作日` : `${projects.length}个项目`}
              ，合计 {selectedMonth 
                ? projects.reduce((sum, p) => sum + (p.monthly_total_sum || 0), 0)
                : projects.reduce((sum, p) => sum + p.annual_total, 0)} 小时
            </span>
          )}
        </div>

        {/* 项目列表 */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>加载中...</div>
        ) : projects.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
            <p style={{ color: '#6b7280', marginBottom: '16px' }}>暂无工时数据</p>
            <button onClick={handleAllocateAll} className="btn-primary">开始归集</button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {projects.map(proj => {
              const projDays = calcDays(proj.start_date, proj.end_date);
              const hasData = Object.keys(proj.members).length > 0 && 
                (selectedMonth ? (proj.monthly_total_sum || 0) > 0 : proj.annual_total > 0);
              
              return (
                <div key={proj.id} className="project-card-wrapper">
                  {/* 项目头部 */}
                  <div className="project-header">
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: '600', margin: 0 }}>{proj.name}</h3>
                      <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                        工期: {proj.start_date.substring(0, 10)} ~ {proj.end_date.substring(0, 10)} ({projDays}天) | 
                        预算: {proj.budget_2026}千元 | 
                        人员: {Object.keys(proj.members).length}人
                        {!hasData && <span style={{ color: '#dc2626', marginLeft: '8px' }}>⚠️ 无工时数据</span>}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: hasData ? '#2563eb' : '#9ca3af' }}>
                        {selectedMonth ? (proj.monthly_total_sum || 0) : proj.annual_total}h
                      </div>
                      <div style={{ fontSize: '12px', color: '#6b7280' }}>
                        {selectedMonth ? '本月合计' : '年度合计'}
                      </div>
                    </div>
                  </div>
                  
                  {/* 人员表格 */}
                  {hasData && (
                    <div style={{ overflow: 'auto', maxHeight: '400px' }}>
                      <table className="hours-table">
                        <thead>
                          <tr>
                            <th className="sticky-left">人员</th>
                            {selectedMonth 
                              ? proj.workdays?.map(day => (
                                  <th key={day} className="day-header">{day}日</th>
                                ))
                              : monthNames.map((name, i) => (
                                  <th key={i}>{name}</th>
                                ))
                            }
                            <th className="sticky-right">合计</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(proj.members).map(([name, data]) => {
                            const total = selectedMonth 
                              ? data.total_hours 
                              : Object.values(data.monthly_hours || {}).reduce((a, b) => a + b, 0);
                            if (total === 0) return null;
                            
                            return (
                              <tr key={name}>
                                <td className="sticky-left member-name">
                                  {name}
                                  {data.is_manager && <span className="manager-tag">管理</span>}
                                  {data.employment_end && <span className="离职-tag">离职</span>}
                                </td>
                                {selectedMonth 
                                  ? proj.workdays?.map(day => {
                                      const h = data.daily_hours?.[day] || 0;
                                      return (
                                        <td key={day} className={h > 0 ? 'has-hours' : 'no-hours'}>
                                          {h > 0 ? `${h}h` : '-'}
                                        </td>
                                      );
                                    })
                                  : monthNames.map((_, i) => {
                                      const h = data.monthly_hours?.[i + 1] || 0;
                                      return (
                                        <td key={i} className={h > 0 ? 'has-hours' : 'no-hours'}>
                                          {h > 0 ? `${h}h` : '-'}
                                        </td>
                                      );
                                    })
                                }
                                <td className="sticky-right total-cell">
                                  {total}h
                                </td>
                              </tr>
                            );
                          })}
                          {/* 合计行 */}
                          <tr className="summary-row">
                            <td className="sticky-left">合计</td>
                            {selectedMonth 
                              ? proj.workdays?.map(day => {
                                  const h = proj.daily_total?.[day] || 0;
                                  return (
                                    <td key={day} className={h > 0 ? 'summary-hours' : ''}>
                                      {h > 0 ? `${h}h` : '-'}
                                    </td>
                                  );
                                })
                              : monthNames.map((_, i) => {
                                  const h = proj.monthly_total?.[i + 1] || 0;
                                  return (
                                    <td key={i} className={h > 0 ? 'summary-hours' : ''}>
                                      {h > 0 ? `${h}h` : '-'}
                                    </td>
                                  );
                                })
                            }
                            <td className="sticky-right grand-total">
                              {selectedMonth ? (proj.monthly_total_sum || 0) : proj.annual_total}h
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>

      <style>{`
        .btn-primary {
          background: #2563eb;
          color: white;
          padding: 10px 20px;
          border-radius: 8px;
          border: none;
          cursor: pointer;
        }
        .btn-primary:hover { background: #1d4ed8; }
        
        .btn-outline {
          background: white;
          color: #374151;
          padding: 10px 20px;
          border-radius: 8px;
          border: 1px solid #d1d5db;
          cursor: pointer;
        }
        .btn-outline:hover { background: #f9fafb; }
        
        .select-input {
          padding: 8px 16px;
          border-radius: 8px;
          border: 1px solid #d1d5db;
          background: white;
        }
        
        .alert-error {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 16px;
          display: flex;
          justify-content: space-between;
        }
        
        .project-card-wrapper {
          background: #fff;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
        }
        
        .project-header {
          padding: 16px;
          background: #f9fafb;
          borderBottom: 1px solid #e5e7eb;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        .hours-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        
        .hours-table th {
          padding: 10px 6px;
          background: #f9fafb;
          border-bottom: 2px solid #e5e7eb;
          text-align: center;
          font-weight: 600;
          color: #374151;
        }
        
        .hours-table td {
          padding: 8px 6px;
          border-bottom: 1px solid #f3f4f6;
          text-align: center;
        }
        
        .sticky-left {
          position: sticky;
          left: 0;
          background: #fff;
          z-index: 1;
          text-align: left;
          padding-left: 12px;
        }
        
        .sticky-right {
          position: sticky;
          right: 0;
          background: #eff6ff;
          z-index: 1;
        }
        
        .day-header { min-width: 40px; }
        
        .member-name { font-weight: 500; }
        
        .manager-tag {
          margin-left: 4px;
          font-size: 11px;
          color: #2563eb;
          background: #dbeafe;
          padding: 2px 4px;
          border-radius: 4px;
        }
        
        .离职-tag {
          margin-left: 4px;
          font-size: 11px;
          color: #dc2626;
        }
        
        .has-hours {
          background: #f0fdf4;
          color: #16a34a;
          font-weight: 500;
        }
        
        .no-hours {
          color: #9ca3af;
        }
        
        .total-cell {
          font-weight: 600;
          color: #2563eb;
        }
        
        .summary-row {
          background: #f9fafb;
        }
        
        .summary-row td {
          font-weight: 600;
        }
        
        .summary-hours {
          color: #16a34a;
        }
        
        .grand-total {
          font-weight: bold;
          color: #1d4ed8;
          background: #dbeafe;
        }
      `}</style>
    </div>
  );
}