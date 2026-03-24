import React from 'react'

const variants = {
  success: { bg: '#16A34A22', color: '#16A34A', border: '#16A34A44' },
  danger: { bg: '#DC262622', color: '#DC2626', border: '#DC262644' },
  warning: { bg: '#D9770622', color: '#D97706', border: '#D9770644' },
  accent: { bg: '#2563EB22', color: '#2563EB', border: '#2563EB44' },
  muted: { bg: '#33333366', color: '#A0A0A0', border: '#444444' },
}

export default function Badge({ children, variant = 'muted', style = {} }) {
  const v = variants[variant] || variants.muted
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '3px 8px',
      borderRadius: '9999px',
      fontSize: '11px',
      fontWeight: '600',
      letterSpacing: '0.3px',
      backgroundColor: v.bg,
      color: v.color,
      border: `1px solid ${v.border}`,
      ...style,
    }}>
      {children}
    </span>
  )
}
