import { useAppStore } from '../store'

interface MobileNavProps {
  active: 'home' | 'daily' | 'projects' | 'tracking' | 'quality' | 'dashboard'
}

export default function MobileNav({ active }: MobileNavProps) {
  const { user } = useAppStore()
  const userRoleId = user?.role_id || 13

  const allItems = [
    { key: 'home', href: '/agent/', icon: '🏠', label: '个人', roles: [11, 13, 14, 15, 16] },
    { key: 'daily', href: '/agent/daily', icon: '📝', label: '日报', roles: [11, 13, 14, 15, 16] },
    { key: 'projects', href: '/agent/projects', icon: '📊', label: '项目', roles: [11, 13, 14, 15, 16] },
    { key: 'tracking', href: '/agent/tracking', icon: '📍', label: '追踪', roles: [11, 13, 14, 15, 16] },
    { key: 'quality', href: '/agent/quality', icon: '🎯', label: '质量', roles: [11, 13, 14, 15, 16] },
    { key: 'dashboard', href: '/agent/dashboard', icon: '📈', label: '看板', roles: [11, 13, 14, 15, 16, 17] },
  ]

  const items = allItems.filter(item => item.roles.includes(userRoleId))

  return (
    <nav className="mobile-nav">
      {items.map(item => (
        <a 
          key={item.key}
          href={item.href} 
          className={`mobile-nav-item ${active === item.key ? 'active' : ''}`}
        >
          <span className="mobile-nav-icon">{item.icon}</span>
          <span>{item.label}</span>
        </a>
      ))}
    </nav>
  )
}
