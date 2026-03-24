import React from 'react'

export default function Card({ children, style = {}, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        backgroundColor: '#242424',
        borderRadius: '12px',
        padding: '16px',
        border: '1px solid #333333',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      {children}
    </div>
  )
}
