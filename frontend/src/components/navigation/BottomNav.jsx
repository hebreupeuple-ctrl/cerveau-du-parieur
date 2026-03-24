import React from 'react'
import {
  TrendingUp,
  Calendar,
  BarChart2,
  Search,
  Settings
} from 'lucide-react'

const navItems = [
  { id: 'today', label: "Aujourd'hui", Icon: Calendar },
  { id: 'performance', label: 'Performance', Icon: TrendingUp },
  { id: 'historique', label: 'Historique', Icon: BarChart2 },
  { id: 'analyse', label: 'Analyse', Icon: Search },
  { id: 'parametres', label: 'Paramètres', Icon: Settings },
]

export default function BottomNav({ active, onChange }) {
  return (
    <nav style={{
      position: 'fixed',
      bottom: 0,
      left: '50%',
      transform: 'translateX(-50%)',
      width: '100%',
      maxWidth: '430px',
      backgroundColor: '#1A1A1A',
      borderTop: '1px solid #333333',
      display: 'flex',
      justifyContent: 'space-around',
      alignItems: 'center',
      padding: '8px 0 12px',
      zIndex: 100,
    }}>
      {navItems.map(({ id, label, Icon }) => {
        const isActive = active === id
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 12px',
              borderRadius: '8px',
              color: isActive ? '#2563EB' : '#666666',
              transition: 'color 0.2s',
            }}
          >
            <Icon size={22} strokeWidth={isActive ? 2.5 : 1.8} />
            <span style={{
              fontSize: '10px',
              fontWeight: isActive ? '600' : '400',
              letterSpacing: '0.3px',
            }}>
              {label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
