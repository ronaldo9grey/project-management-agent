import { useState } from 'react'

export default function Report() {
  const [activeSection, setActiveSection] = useState('overview')

  const sections = [
    { id: 'overview', title: '一、使用概况' },
    { id: 'ai-usage', title: '二、AI解析使用' },
    { id: 'project-match', title: '三、项目匹配率' },
    { id: 'project-stats', title: '四、项目参与度' },
    { id: 'data-fix', title: '五、数据修复记录' },
    { id: 'alias', title: '六、项目别名表' },
    { id: 'features', title: '七、便利功能' },
    { id: 'suggestions', title: '八、使用建议' },
    { id: 'summary', title: '九、总结' },
  ]

  return (
    <div className="page-container">
      {/* 侧边导航 */}
      <div style={{
        position: 'fixed',
        left: 0,
        top: '60px',
        bottom: 0,
        width: '200px',
        background: '#f8fafc',
        borderRight: '1px solid #e5e7eb',
        overflowY: 'auto',
        padding: '20px 0'
      }}>
        <div style={{ padding: '0 16px', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '14px', color: '#64748b', fontWeight: '600' }}>
            📋 系统复盘报告
          </h2>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
            2026年4月统计
          </p>
        </div>
        <nav>
          {sections.map(section => (
            <a
              key={section.id}
              href={`#${section.id}`}
              onClick={(e) => {
                e.preventDefault()
                setActiveSection(section.id)
                document.getElementById(section.id)?.scrollIntoView({ behavior: 'smooth' })
              }}
              style={{
                display: 'block',
                padding: '10px 16px',
                color: activeSection === section.id ? '#3b82f6' : '#475569',
                background: activeSection === section.id ? '#eff6ff' : 'transparent',
                borderLeft: activeSection === section.id ? '3px solid #3b82f6' : '3px solid transparent',
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {section.title}
            </a>
          ))}
        </nav>
      </div>

      {/* 主内容区 */}
      <div style={{
        marginLeft: '200px',
        padding: '40px 60px',
        maxWidth: '900px'
      }}>
        {/* 标题 */}
        <header style={{ marginBottom: '40px', borderBottom: '2px solid #e5e7eb', paddingBottom: '20px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>
            项目智能体系统使用复盘报告
          </h1>
          <div style={{ fontSize: '14px', color: '#64748b' }}>
            <span>报告日期：2026年5月7日</span>
            <span style={{ margin: '0 12px' }}>|</span>
            <span>统计周期：2026年4月1日 - 2026年5月6日</span>
          </div>
        </header>

        {/* 一、使用概况 */}
        <section id="overview" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>一</span>
            使用概况
          </h2>
          
          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>1.1 活跃用户统计</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#f0f9ff', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#0284c7' }}>33</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>系统注册用户</div>
            </div>
            <div style={{ background: '#f0fdf4', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#16a34a' }}>15</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>活跃用户</div>
            </div>
            <div style={{ background: '#fef3c7', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#d97706' }}>2105.3h</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>累计工时（4月）</div>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>排名</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>姓名</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>部门</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>日报天数</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>总工时</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { rank: 1, name: '罗小向', dept: '经营管理室', days: 20, hours: '158h' },
                  { rank: 2, name: '李唯', dept: '装备改善部', days: 20, hours: '155h' },
                  { rank: 3, name: '梁叶凌', dept: '经营管理室', days: 20, hours: '181h' },
                  { rank: 4, name: '何旭', dept: '经营管理室', days: 19, hours: '152h' },
                  { rank: 5, name: '吴成荣', dept: '经营管理室', days: 19, hours: '117h' },
                ].map(row => (
                  <tr key={row.rank}>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>{row.rank}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', fontWeight: '500' }}>{row.name}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>{row.dept}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>{row.days}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', fontWeight: '600', color: '#3b82f6' }}>{row.hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 二、AI智能解析使用情况 */}
        <section id="ai-usage" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>二</span>
            AI智能解析使用情况
          </h2>

          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>🎯</span>
              <div>
                <strong style={{ color: '#166534' }}>结论</strong>
                <p style={{ margin: '4px 0 0', color: '#15803d', fontSize: '14px' }}>
                  AI智能解析已成为主要填写方式，用户认可度高。
                </p>
              </div>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>指标</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>数值</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>使用AI解析的日报（有原始输入）</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', fontWeight: '700', color: '#16a34a' }}>97.5%</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>早期数据（无原始输入记录）</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', color: '#64748b' }}>2.5%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '12px', background: '#f8fafc', padding: '12px', borderRadius: '6px' }}>
            注：2.5%无原始输入的日报为早期系统数据（张钢、何宾4月初记录），当时系统未保存用户输入原文。
          </p>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', margin: '24px 0 16px' }}>2.2 解析特征分析</h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>输入特征</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>占比</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>包含时间段（上午/下午）</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>45.9%</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>包含时间数字（8:15-12:00）</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>25.6%</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>无时间标识</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', color: '#dc2626', fontWeight: '600' }}>27.8%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px', marginTop: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>⚠️</span>
              <div>
                <strong style={{ color: '#991b1b' }}>发现</strong>
                <p style={{ margin: '4px 0 0', color: '#b91c1c', fontSize: '14px' }}>
                  27.8% 的日报输入没有明确时间标识，导致工时分配不够精确。
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 三、项目匹配率分析 */}
        <section id="project-match" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>三</span>
            项目匹配率分析
          </h2>

          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>🚨</span>
              <div>
                <strong style={{ color: '#991b1b' }}>问题</strong>
                <p style={{ margin: '4px 0 0', color: '#b91c1c', fontSize: '14px' }}>
                  项目匹配率偏低，任务关联率极低，大量工作无法追溯到具体项目。
                </p>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#f0f9ff', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#0369a1' }}>45.8%</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>项目匹配率</div>
            </div>
            <div style={{ background: '#fef3c7', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#d97706' }}>0.1%</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>任务关联率</div>
            </div>
            <div style={{ background: '#fee2e2', borderRadius: '8px', padding: '20px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: '700', color: '#dc2626' }}>403</div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>未匹配工作项</div>
            </div>
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>3.2 未匹配工作项分布</h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>姓名</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>未匹配项数</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>未匹配工时</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: '龙华强', items: 81, hours: '126.7h' },
                  { name: '梁叶凌', items: 75, hours: '175.8h' },
                  { name: '张迪', items: 38, hours: '95.7h' },
                  { name: '吴成荣', items: 37, hours: '68.8h' },
                  { name: '何宾', items: 34, hours: '70.6h' },
                ].map(row => (
                  <tr key={row.name}>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', fontWeight: '500' }}>{row.name}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>{row.items}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', color: '#dc2626' }}>{row.hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', margin: '24px 0 16px' }}>3.3 未匹配的常见工作内容</h3>
          
          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px' }}>
            <p style={{ fontSize: '14px', color: '#475569', marginBottom: '12px' }}>高频未匹配关键词：</p>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px', color: '#334155' }}>
              <li style={{ marginBottom: '8px' }}><code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>施印材料审核及盖章</code>（20次）</li>
              <li style={{ marginBottom: '8px' }}><code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>开早会/早会</code>（20次）</li>
              <li style={{ marginBottom: '8px' }}><code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>晚会</code>（3次）</li>
              <li style={{ marginBottom: '8px' }}><code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>处理日常事务</code>（2次）</li>
              <li><code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>开会</code>（2次）</li>
            </ul>
          </div>

          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '16px', marginTop: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>💡</span>
              <div>
                <strong style={{ color: '#166534' }}>分析</strong>
                <p style={{ margin: '4px 0 0', color: '#15803d', fontSize: '14px' }}>
                  这些工作属于行政管理类，不属于具体项目，归类为「其他工作」是合理的。
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 四、项目参与度分析 */}
        <section id="project-stats" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>四</span>
            项目参与度分析
          </h2>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>4.1 热门项目排行</h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>项目名称</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>负责人</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>工作项数</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>参与人数</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>累计工时</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: '落地锰转化锰锭项目', leader: '张钢', items: 58, members: 6, hours: '212.8h' },
                  { name: '德保铝厂全厂电机节能改造', leader: '何宾', items: 47, members: 7, hours: '141h' },
                  { name: '隆林铝厂空压机集中控制项目', leader: '周贵平', items: 43, members: 5, hours: '177h' },
                  { name: '田阳铝厂脱硫浆液循环泵节能', leader: '顾锦荣', items: 40, members: 7, hours: '167h' },
                  { name: '田林铝厂供电整流PLC稳定性', leader: '陆宏东', items: 34, members: 6, hours: '89h' },
                ].map(row => (
                  <tr key={row.name}>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', fontWeight: '500' }}>{row.name}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>{row.leader}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>{row.items}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>{row.members}</td>
                    <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right', fontWeight: '600', color: '#3b82f6' }}>{row.hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 五、数据质量修复记录 */}
        <section id="data-fix" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>五</span>
            数据质量修复记录（2026年5月7日）
          </h2>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>5.1 工时精度问题修复</h3>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>问题类型</th>
                  <th style={{ padding: '12px', textAlign: 'right', borderBottom: '2px solid #e2e8f0' }}>修正数量</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>涉及用户</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>精度误差（≤0.02）</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>12条</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '13px' }}>罗小向、张迪、何旭、陆宏东、梁叶凌、何宾、李唯</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>负数工时</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>4条</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '13px' }}>龙华强、陆宏东、梁叶凌</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>工时为0</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', textAlign: 'right' }}>5条日报</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '13px' }}>薛闯4/1、薛闯4/21、龙华强4/28/29/30</td>
                </tr>
                <tr style={{ background: '#f0f9ff' }}>
                  <td style={{ padding: '12px', borderBottom: '2px solid #e2e8f0', fontWeight: '600' }}>合计</td>
                  <td style={{ padding: '12px', borderBottom: '2px solid #e2e8f0', textAlign: 'right', fontWeight: '700' }}>21条</td>
                  <td style={{ padding: '12px', borderBottom: '2px solid #e2e8f0' }}>-</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', margin: '24px 0 16px' }}>5.2 项目匹配错误修复</h3>
          
          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#334155', marginBottom: '12px' }}>张钢（锰锭相关）</h4>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>德保铝厂化锰筑炉、铁锭模、锰锭试制、德保铝厂化锰铸锰锭
            </p>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>正确项目：</strong>落地锰转化锰锭项目(34)
            </p>
            <p style={{ fontSize: '13px', color: '#0369a1' }}>
              修正7条记录，共40.5小时
            </p>
          </div>

          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#334155', marginBottom: '12px' }}>李唯（抓斗/炭渣/中频炉）</h4>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>天车抓斗改进、田林电解天车抓斗 → 项目14（一种新型电解铝多功能天车抓斗结构的设计及产业化）
            </p>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>电解质炭渣处理 → 项目32（铝电解碳渣低温氧化处理技术）
            </p>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>中频炉、精铝车间 → 项目34（落地锰转化锰锭项目）
            </p>
            <p style={{ fontSize: '13px', color: '#0369a1' }}>
              修正8条记录，共17小时
            </p>
          </div>

          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#334155', marginBottom: '12px' }}>张迪（炭渣/锰渣）</h4>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>炭渣项目、炭渣试验 → 项目32（铝电解碳渣低温氧化处理技术）
            </p>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>锰渣专题、锰渣固化、锰渣无害化 → 项目33（电解锰渣无害化处理项目）
            </p>
            <p style={{ fontSize: '13px', color: '#0369a1' }}>
              修正8条记录，共15.5小时
            </p>
          </div>

          <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#334155', marginBottom: '12px' }}>薛闯（电解槽新烟管）</h4>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>关键词：</strong>电解槽新烟管、新烟管软连接
            </p>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              <strong>正确项目：</strong>600KA槽上部烟气治理的技术研究(12)
            </p>
            <p style={{ fontSize: '13px', color: '#0369a1' }}>
              修正12条记录，共47小时
            </p>
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', margin: '24px 0 16px' }}>5.3 工时统计口径统一</h3>
          
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '16px' }}>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#92400e' }}>
              <strong>问题：</strong>人员维度和组织维度总工时小数点不一致（2105.3 vs 2105.1）
            </p>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#92400e' }}>
              <strong>原因：</strong>分组数据先四舍五入再累加，产生精度累积误差
            </p>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#92400e' }}>
              <strong>修复：</strong>累加原始精度工时，最后统一四舍五入
            </p>
            <p style={{ margin: 0, fontSize: '14px', color: '#15803d', fontWeight: '600' }}>
              结果：两个维度工时统一为 2105.3h
            </p>
          </div>
        </section>

        {/* 六、项目别名映射表 */}
        <section id="alias" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>六</span>
            项目别名映射表
          </h2>

          <p style={{ fontSize: '14px', color: '#475569', marginBottom: '16px' }}>
            系统已内置以下项目别名，用户可直接使用：
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>常用别名</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>对应项目</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['炭渣项目、炭渣试验', '铝电解碳渣低温氧化处理技术'],
                  ['电解槽新烟管、新烟管软连接', '600KA槽上部烟气治理的技术研究'],
                  ['锰锭试制、铁锭模、德保铝厂化锰筑炉', '落地锰转化锰锭项目'],
                  ['田林铝厂供电整流', '田林铝厂供电整流PLC控制系统稳定性研发项目'],
                  ['隆林铝厂空压机', '隆林铝厂空压机集中控制项目研究'],
                  ['隆林铝厂除尘器', '隆林铝厂除尘器布袋脉冲精准控制研究'],
                  ['隆林铝厂整流系统', '隆林铝厂整流系统总调PLC升级改造项目'],
                  ['电解铝多功能天车抓斗、田林电解天车抓斗', '一种新型电解铝多功能天车抓斗结构的设计及产业化'],
                  ['锰渣专题、锰渣固化、锰渣无害化', '电解锰渣无害化处理项目'],
                ].map(([alias, project]) => (
                  <tr key={alias}>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #e2e8f0' }}>
                      <code style={{ background: '#e2e8f0', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>{alias}</code>
                    </td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #e2e8f0' }}>{project}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 七、系统便利功能说明 */}
        <section id="features" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>七</span>
            系统便利功能说明
          </h2>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>🚀 快捷操作功能</h3>

          <div style={{ display: 'grid', gap: '16px' }}>
            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
                1. 复制上次日报
              </h4>
              <p style={{ fontSize: '13px', color: '#475569', margin: '0 0 8px' }}>
                <strong>入口：</strong>日报页面顶部「复制上次」按钮
              </p>
              <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                <strong>适用场景：</strong>工作内容相似的连续工作日，如「项目A图纸设计」持续多天
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
                2. 历史日报快速查看
              </h4>
              <p style={{ fontSize: '13px', color: '#475569', margin: '0 0 8px' }}>
                <strong>入口：</strong>日报页面下方「历史记录」区域
              </p>
              <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                <strong>功能：</strong>点击历史日报可直接查看详情，支持快速复制内容
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
                3. 智能解析进度提示
              </h4>
              <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                <strong>功能：</strong>解析时显示「AI 正在识别项目和任务（预计 10-30 秒）」，让用户知道需要等待，避免误认为卡死
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
                4. 项目别名自动匹配
              </h4>
              <p style={{ fontSize: '13px', color: '#475569', margin: '0 0 8px' }}>
                <strong>功能：</strong>输入「炭渣项目」「锰锭试制」等别名，系统自动匹配正式项目
              </p>
              <p style={{ fontSize: '13px', color: '#0369a1', margin: 0 }}>
                <strong>新增别名：</strong>本次新增17个常用别名（见第六章）
              </p>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '8px', padding: '16px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>
                5. 工时自动计算
              </h4>
              <p style={{ fontSize: '13px', color: '#475569', margin: '0 0 8px' }}>
                <strong>功能：</strong>用户只需输入时间段，系统自动扣除午休（12:00-13:45）
              </p>
              <p style={{ fontSize: '13px', color: '#475569', margin: 0 }}>
                <strong>默认规则：</strong>开始时间早于08:15时，自动设为08:15
              </p>
            </div>
          </div>
        </section>

        {/* 八、系统效率提升建议 */}
        <section id="suggestions" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>八</span>
            系统效率提升建议
          </h2>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', marginBottom: '16px' }}>🎯 给用户的建议</h3>

          <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#0369a1', marginBottom: '12px' }}>1. 提高项目匹配率</h4>
            <p style={{ fontSize: '13px', color: '#0c4a6e', marginBottom: '12px' }}>
              <strong>问题：</strong>45.8%的工作项未匹配到项目，导致工时统计不准确。
            </p>
            <p style={{ fontSize: '13px', color: '#0c4a6e', marginBottom: '8px' }}><strong>建议：</strong></p>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#0c4a6e' }}>
              <li style={{ marginBottom: '6px' }}>✅ 在日报开头明确标注项目名称，如「<strong>德保铝厂电机节能项目</strong>：上午图纸设计4小时」</li>
              <li style={{ marginBottom: '6px' }}>✅ 使用项目别名，系统已支持：「炭渣项目」「锰锭试制」「电解槽新烟管」等</li>
              <li>✅ 对于非项目工作（开会、行政），在开头写「其他工作」或「日常事务」</li>
            </ul>
          </div>

          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#92400e', marginBottom: '12px' }}>2. 规范时间表述</h4>
            <p style={{ fontSize: '13px', color: '#78350f', marginBottom: '12px' }}>
              <strong>问题：</strong>27.8%的日报没有明确时间标识。
            </p>
            <p style={{ fontSize: '13px', color: '#78350f', marginBottom: '8px' }}><strong>建议：</strong></p>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#78350f' }}>
              <li style={{ marginBottom: '6px' }}>✅ 使用标准格式：「上午8:15-12:00 xxx；下午13:45-18:00 xxx」</li>
              <li style={{ marginBottom: '6px' }}>✅ 系统会自动扣除午休时间（12:00-13:45）</li>
              <li>✅ 加班需明确标注：「加班2小时」或「晚上20:00-22:00」</li>
            </ul>
          </div>

          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#166534', marginBottom: '12px' }}>3. 提高工作项粒度</h4>
            <p style={{ fontSize: '13px', color: '#14532d', marginBottom: '12px' }}>
              <strong>问题：</strong>每天只记录1-2项工作，任务关联困难。
            </p>
            <p style={{ fontSize: '13px', color: '#14532d', marginBottom: '8px' }}><strong>建议：</strong></p>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#14532d' }}>
              <li style={{ marginBottom: '6px' }}>✅ 将一天的工作拆分为多个具体事项</li>
              <li style={{ marginBottom: '6px' }}>✅ 每个事项关联具体任务（如「图纸设计」「现场调试」「会议讨论」）</li>
              <li>✅ 示例：「上午8:15-10:00 图纸设计；10:00-12:00 修改方案」</li>
            </ul>
          </div>

          <div style={{ background: '#fdf4ff', border: '1px solid #f0abfc', borderRadius: '8px', padding: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#86198d', marginBottom: '12px' }}>4. 善用便利功能</h4>
            <p style={{ fontSize: '13px', color: '#701a75', marginBottom: '8px' }}><strong>建议：</strong></p>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#701a75' }}>
              <li style={{ marginBottom: '6px' }}>✅ 工作内容相似时，使用「复制上次」快速填充</li>
              <li style={{ marginBottom: '6px' }}>✅ 使用项目别名而非完整项目名，输入更快</li>
              <li>✅ 参考历史日报，保持描述风格一致</li>
            </ul>
          </div>

          <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#334155', margin: '24px 0 16px' }}>📈 系统改进记录</h3>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>改进项</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e2e8f0' }}>说明</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>工时精度修复</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>负数工时、0工时、浮点数精度问题已全部修正</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>项目匹配优化</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>扩充别名映射表，新增17个常用别名</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>统计口径统一</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>人员维度和项目维度工时统计口径一致</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>AI解析增强</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>默认开始时间设为08:15，工时计算更准确</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>便利功能</td>
                  <td style={{ padding: '12px', borderBottom: '1px solid #e2e8f0' }}>复制上次日报、历史记录快速查看、解析进度提示</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 九、总结 */}
        <section id="summary" style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1e293b', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ background: '#3b82f6', color: 'white', width: '28px', height: '28px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>九</span>
            总结
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '16px' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#166534', marginBottom: '12px' }}>✅ 做得好</h4>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#15803d' }}>
                <li style={{ marginBottom: '6px' }}>AI解析使用率97.5%，用户高度认可</li>
                <li style={{ marginBottom: '6px' }}>日均活跃用户稳定（13-14人）</li>
                <li>工时记录完整，精度问题已修正</li>
              </ul>
            </div>

            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#991b1b', marginBottom: '12px' }}>⚠️ 待改进</h4>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#b91c1c' }}>
                <li style={{ marginBottom: '6px' }}>项目匹配率45.8%，需提高</li>
                <li style={{ marginBottom: '6px' }}>任务关联率仅0.1%，基本未使用</li>
                <li style={{ marginBottom: '6px' }}>时间表述不规范（27.8%无时间标识）</li>
                <li>工作项粒度粗（33.8%每天仅2项）</li>
              </ul>
            </div>
          </div>

          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#1e40af', marginBottom: '12px' }}>🎯 下一步</h4>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#1d4ed8' }}>
              <li style={{ marginBottom: '6px' }}>发布使用指南，规范日报格式</li>
              <li style={{ marginBottom: '6px' }}>持续扩充项目别名映射表</li>
              <li style={{ marginBottom: '6px' }}>优化AI任务匹配逻辑</li>
              <li>完善便利功能，提升填写效率</li>
            </ul>
          </div>
        </section>

        {/* 页脚 */}
        <footer style={{ borderTop: '2px solid #e5e7eb', paddingTop: '20px', color: '#64748b', fontSize: '13px' }}>
          <p><strong>报告生成时间：</strong>2026年5月7日 17:25</p>
          <p><strong>数据来源：</strong>项目智能体系统数据库</p>
        </footer>
      </div>
    </div>
  )
}