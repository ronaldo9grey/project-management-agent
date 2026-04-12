interface MobileNavProps {
  active: 'home' | 'daily' | 'projects' | 'dashboard' | 'tracking'
}

export default function MobileNav({ active }: MobileNavProps) {
  return (
    <nav className="mobile-nav">
      <a href="/agent/" className={`mobile-nav-item ${active === 'home' ? 'active' : ''}`}>
        <span className="mobile-nav-icon">🏠</span>
        <span>个人</span>
      </a>
      <a href="/agent/daily" className={`mobile-nav-item ${active === 'daily' ? 'active' : ''}`}>
        <span className="mobile-nav-icon">📝</span>
        <span>日报</span>
      </a>
      <a href="/agent/projects" className={`mobile-nav-item ${active === 'projects' ? 'active' : ''}`}>
        <span className="mobile-nav-icon">📊</span>
        <span>项目</span>
      </a>
      <a href="/agent/tracking" className={`mobile-nav-item ${active === 'tracking' ? 'active' : ''}`}>
        <span className="mobile-nav-icon">📍</span>
        <span>追踪</span>
      </a>
      <a href="/agent/dashboard" className={`mobile-nav-item ${active === 'dashboard' ? 'active' : ''}`}>
        <span className="mobile-nav-icon">📈</span>
        <span>看板</span>
      </a>
    </nav>
  )
}
