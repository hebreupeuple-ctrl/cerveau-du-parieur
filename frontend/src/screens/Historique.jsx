import React, { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Clock, CheckCircle, XCircle, MinusCircle, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Skeleton from '../components/shared/Skeleton.jsx'
import EmptyState from '../components/shared/EmptyState.jsx'
import { formatDate, formatHeure, formatCote } from '../utils/formatters.js'
import api from '../services/api.js'

const FILTERS = [
  { id: 'all',      label: 'Tous' },
  { id: 'en_cours', label: 'En cours' },
  { id: 'won',      label: 'Gagnés' },
  { id: 'lost',     label: 'Perdus' },
  { id: 'void',     label: 'Annulés' },
]

const MARKET_LABELS = {
  over25:    'Plus de 2.5 buts',
  over15:    'Plus de 1.5 buts',
  over35:    'Plus de 3.5 buts',
  over45:    'Plus de 4.5 buts',
  btts:      'Les deux équipes marquent',
  over15_ht: 'Plus de 1.5 buts (MT)',
  '1x2_home':  'Victoire domicile',
  '1x2_draw':  'Match nul',
  '1x2_away':  'Victoire extérieur',
}

function StatusIcon({ status, size = 16 }) {
  if (status === 'won')   return <CheckCircle size={size} color="#16A34A" />
  if (status === 'lost')  return <XCircle size={size} color="#DC2626" />
  if (status === 'void')  return <MinusCircle size={size} color="#6B7280" />
  return <Clock size={size} color="#D97706" />
}

function StatBox({ label, value, sub, color = '#F5F5F5' }) {
  return (
    <div style={{ textAlign: 'center', flex: 1 }}>
      <div style={{ fontSize: '20px', fontWeight: '700', color }}>{value}</div>
      <div style={{ fontSize: '11px', color: '#666666', marginTop: '2px' }}>{label}</div>
      {sub && <div style={{ fontSize: '11px', color: '#444', marginTop: '1px' }}>{sub}</div>}
    </div>
  )
}

function PronosticRow({ item }) {
  const [open, setOpen] = useState(false)

  const isWon  = item.status === 'won'
  const isLost = item.status === 'lost'
  const isVoid = item.status === 'void'
  const enCours = item.status === 'placed' || item.status === 'pending'

  const profitColor = isWon ? '#16A34A' : isLost ? '#DC2626' : '#6B7280'
  const profitStr = item.actual_profit != null
    ? `${item.actual_profit >= 0 ? '+' : ''}${item.actual_profit.toFixed(2)}€`
    : null

  return (
    <div style={{
      backgroundColor: '#242424',
      borderRadius: '10px',
      border: '1px solid #333333',
      marginBottom: '8px',
      overflow: 'hidden',
    }}>
      {/* Ligne principale */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{ padding: '14px 16px', cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <div style={{ paddingTop: '2px' }}>
            <StatusIcon status={item.status} size={18} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Match */}
            <div style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5', marginBottom: '2px' }}>
              {item.match.home_team} <span style={{ color: '#666' }}>vs</span> {item.match.away_team}
            </div>
            {/* Marché + ligue */}
            <div style={{ fontSize: '12px', color: '#888888' }}>
              {MARKET_LABELS[item.market] || item.market}
              <span style={{ margin: '0 6px', color: '#444' }}>·</span>
              {item.match.league}
            </div>
            {/* Date + score si disponible */}
            <div style={{ fontSize: '11px', color: '#555555', marginTop: '3px', display: 'flex', gap: '8px' }}>
              <span>{formatDate(item.match.kickoff_timestamp)} {formatHeure(item.match.kickoff_timestamp)}</span>
              {item.match.score && (
                <span style={{ fontWeight: '600', color: '#888' }}>{item.match.score}</span>
              )}
            </div>
          </div>
          {/* Profit / statut */}
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            {profitStr ? (
              <div style={{ fontSize: '15px', fontWeight: '700', color: profitColor }}>
                {profitStr}
              </div>
            ) : enCours ? (
              <div style={{ fontSize: '11px', color: '#D97706', fontWeight: '600' }}>
                {item.status === 'placed' ? 'Misé' : 'En attente'}
              </div>
            ) : null}
            {item.actual_stake != null && (
              <div style={{ fontSize: '11px', color: '#555', marginTop: '2px' }}>
                Mise {item.actual_stake.toFixed(2)}€
              </div>
            )}
            <div style={{ marginTop: '4px', display: 'flex', justifyContent: 'flex-end' }}>
              {open ? <ChevronUp size={14} color="#555" /> : <ChevronDown size={14} color="#555" />}
            </div>
          </div>
        </div>
      </div>

      {/* Détail expandable */}
      {open && (
        <div style={{
          borderTop: '1px solid #333333',
          padding: '12px 16px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '10px',
        }}>
          {[
            { label: 'Probabilité modèle', value: `${Math.round((item.model_probability || 0) * 100)}%` },
            { label: 'Cote recommandée',   value: formatCote(item.reference_odds) },
            { label: 'Cote jouée',         value: formatCote(item.actual_odds) },
            { label: 'Valeur espérée',     value: item.expected_value != null ? `+${(item.expected_value * 100).toFixed(1)}%` : '—' },
            { label: 'Confiance',          value: item.confidence_score != null ? `${Math.round(item.confidence_score * 100)}%` : '—' },
            { label: 'Mise conseillée',    value: item.recommended_stake != null ? `${item.recommended_stake.toFixed(2)}€` : '—' },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ fontSize: '10px', color: '#555555', marginBottom: '2px' }}>{label}</div>
              <div style={{ fontSize: '13px', color: '#CCCCCC', fontWeight: '600' }}>{value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Historique() {
  const [filter, setFilter]   = useState('all')
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [page, setPage]       = useState(1)

  const fetchHistory = useCallback(async (f, p) => {
    setLoading(true)
    setError(null)
    try {
      const params = { page: p, limit: 20 }
      if (f !== 'all') params.status = f
      const res = await api.get('/pronostics/history', { params })
      setData(res.data)
    } catch (e) {
      setError("Impossible de charger l'historique")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setPage(1)
    fetchHistory(filter, 1)
  }, [filter, fetchHistory])

  const stats = data?.stats
  const items = data?.items || []
  const pagination = data?.pagination

  return (
    <div style={{ padding: '16px', paddingBottom: '32px' }}>
      {/* En-tête */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingTop: '8px', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>Historique</h1>
          <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>Tous vos paris</p>
        </div>
        <button
          onClick={() => fetchHistory(filter, page)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
        >
          <RefreshCw size={18} color="#555" />
        </button>
      </div>

      {/* Stats globales */}
      {stats && (
        <div style={{
          backgroundColor: '#242424',
          borderRadius: '12px',
          border: '1px solid #333',
          padding: '16px',
          marginBottom: '20px',
        }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <StatBox
              label="Gagnés"
              value={stats.won}
              color="#16A34A"
            />
            <div style={{ width: '1px', backgroundColor: '#333' }} />
            <StatBox
              label="Perdus"
              value={stats.lost}
              color="#DC2626"
            />
            <div style={{ width: '1px', backgroundColor: '#333' }} />
            <StatBox
              label="En cours"
              value={stats.en_cours}
              color="#D97706"
            />
            <div style={{ width: '1px', backgroundColor: '#333' }} />
            <StatBox
              label="Win rate"
              value={stats.win_rate != null ? `${Math.round(stats.win_rate * 100)}%` : '—'}
              color={stats.win_rate != null && stats.win_rate > 0.5 ? '#16A34A' : '#F5F5F5'}
            />
          </div>
          <div style={{ borderTop: '1px solid #333', paddingTop: '12px', display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '11px', color: '#555' }}>Profit total</div>
              <div style={{
                fontSize: '16px', fontWeight: '700',
                color: stats.profit_total >= 0 ? '#16A34A' : '#DC2626',
              }}>
                {stats.profit_total >= 0 ? '+' : ''}{stats.profit_total.toFixed(2)}€
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '11px', color: '#555' }}>ROI</div>
              <div style={{
                fontSize: '16px', fontWeight: '700',
                color: stats.roi != null && stats.roi >= 0 ? '#16A34A' : '#DC2626',
              }}>
                {stats.roi != null
                  ? `${stats.roi >= 0 ? '+' : ''}${(stats.roi * 100).toFixed(1)}%`
                  : '—'}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '11px', color: '#555' }}>Mises totales</div>
              <div style={{ fontSize: '16px', fontWeight: '700', color: '#F5F5F5' }}>
                {stats.mises_totales.toFixed(2)}€
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filtres */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', overflowX: 'auto', paddingBottom: '4px' }}>
        {FILTERS.map(f => (
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
            {f.id === 'all' && stats && (
              <span style={{ marginLeft: '4px', color: filter === f.id ? '#AACCFF' : '#444' }}>
                {stats.total}
              </span>
            )}
            {f.id === 'en_cours' && stats && stats.en_cours > 0 && (
              <span style={{ marginLeft: '4px', color: filter === f.id ? '#FFD580' : '#D97706' }}>
                {stats.en_cours}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Liste */}
      {loading && (
        <div>
          {[1, 2, 3, 4].map(i => (
            <div key={i} style={{ marginBottom: '8px' }}>
              <Skeleton height={72} style={{ borderRadius: '10px' }} />
            </div>
          ))}
        </div>
      )}

      {!loading && error && (
        <div style={{
          textAlign: 'center', padding: '32px 16px',
          color: '#DC2626', fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon={TrendingUp}
          title="Aucun pari ici"
          message={
            filter === 'all'
              ? "Vos paris apparaîtront ici après avoir validé votre première recommandation."
              : `Aucun pari avec ce filtre pour l'instant.`
          }
        />
      )}

      {!loading && !error && items.map(item => (
        <PronosticRow key={item.id} item={item} />
      ))}

      {/* Pagination */}
      {!loading && pagination && pagination.pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
          <button
            disabled={page === 1}
            onClick={() => { const p = page - 1; setPage(p); fetchHistory(filter, p) }}
            style={{
              padding: '8px 16px', borderRadius: '8px', border: 'none',
              backgroundColor: page === 1 ? '#1a1a1a' : '#242424',
              color: page === 1 ? '#444' : '#F5F5F5',
              cursor: page === 1 ? 'default' : 'pointer',
              fontSize: '13px',
            }}
          >
            Précédent
          </button>
          <span style={{ lineHeight: '36px', fontSize: '13px', color: '#666' }}>
            {page} / {pagination.pages}
          </span>
          <button
            disabled={page === pagination.pages}
            onClick={() => { const p = page + 1; setPage(p); fetchHistory(filter, p) }}
            style={{
              padding: '8px 16px', borderRadius: '8px', border: 'none',
              backgroundColor: page === pagination.pages ? '#1a1a1a' : '#242424',
              color: page === pagination.pages ? '#444' : '#F5F5F5',
              cursor: page === pagination.pages ? 'default' : 'pointer',
              fontSize: '13px',
            }}
          >
            Suivant
          </button>
        </div>
      )}
    </div>
  )
}
