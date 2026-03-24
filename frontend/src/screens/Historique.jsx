import React, { useState } from 'react'
import { Filter, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'
import EmptyState from '../components/shared/EmptyState.jsx'
import { formatDate, formatHeure, formatCote } from '../utils/formatters.js'

export default function Historique() {
  const [filter, setFilter] = useState('all')

  const filters = [
    { id: 'all', label: 'Tous' },
    { id: 'won', label: 'Gagnés' },
    { id: 'lost', label: 'Perdus' },
    { id: 'pending', label: 'En cours' },
  ]

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ paddingTop: '8px', marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>
          Historique
        </h1>
        <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>
          Tous vos paris
        </p>
      </div>

      <div style={{ display: 'flex', gap: '6px', marginBottom: '20px', overflowX: 'auto', paddingBottom: '4px' }}>
        {filters.map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              whiteSpace: 'nowrap',
              padding: '7px 14px',
              borderRadius: '9999px',
              border: 'none',
              backgroundColor: filter === f.id ? '#2563EB' : '#242424',
              color: filter === f.id ? '#FFFFFF' : '#666666',
              fontSize: '13px',
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <EmptyState
        icon={TrendingUp}
        title="Aucun pari dans l'historique"
        message="Vos paris apparaîtront ici après avoir validé votre première recommandation."
      />
    </div>
  )
}
