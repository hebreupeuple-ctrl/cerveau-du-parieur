import React from 'react'

export default function Skeleton({ width = '100%', height = '16px', style = {} }) {
  return (
    <div style={{
      width,
      height,
      backgroundColor: '#2E2E2E',
      borderRadius: '6px',
      animation: 'pulse 1.5s ease-in-out infinite',
      ...style,
    }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
