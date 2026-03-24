import React from 'react'
import { Moon } from 'lucide-react'

export default function EmptyState({ title, message, icon: Icon = Moon }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '48px 24px',
      gap: '12px',
      textAlign: 'center',
    }}>
      <div style={{
        width: '56px',
        height: '56px',
        borderRadius: '16px',
        backgroundColor: '#242424',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '8px',
      }}>
        <Icon size={28} color="#666666" />
      </div>
      <p style={{ fontSize: '16px', fontWeight: '600', color: '#F5F5F5' }}>
        {title}
      </p>
      <p style={{ fontSize: '13px', color: '#666666', maxWidth: '260px', lineHeight: '1.5' }}>
        {message}
      </p>
    </div>
  )
}
