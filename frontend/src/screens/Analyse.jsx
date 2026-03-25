import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Search, ChevronDown, ChevronUp, CheckCircle, XCircle, Clock, RefreshCw, X } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Skeleton from '../components/shared/Skeleton.jsx'
import EmptyState from '../components/shared/EmptyState.jsx'
import { formatDate, formatHeure, formatCote } from '../utils/formatters.js'
import api from '../services/api.js'

const MODES = [
  { id: 'all',      label: 'Tous' },
  { id: 'upcoming', label: 'À venir' },
  { id: 'past',     label: 'Passés' },
]

function ProbBar({ label, value, color = '#2563EB', correct }) {
  const pct = Math.round((value || 0) * 100)
  return (
    <div style={{ marginBottom: '9px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: '#A0A0A0' }}>{label}</span>
          {correct === true  && <CheckCircle size={12} color="#16A34A" />}
          {correct === false && <XCircle size={12} color="#DC2626" />}
        </div>
        <span style={{ fontSize: '12px', fontWeight: '600', color }}>{pct}%</span>
      </div>
      <div style={{ height: '4px', backgroundColor: '#333', borderRadius: '9999px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', backgroundColor: color, borderRadius: '9999px' }} />
      </div>
    </div>
  )
}

function MarketRow({ m }) {
  const pct = Math.round((m.model_probability || 0) * 100)
  const ev = m.expected_value != null ? `+${(m.expected_value * 100).toFixed(1)}%` : null
  const conf = m.confidence_score != null ? Math.round(m.confidence_score * 100) : null

  const statusColor = m.pronostic_status === 'won'  ? '#16A34A'
                    : m.pronostic_status === 'lost'  ? '#DC2626'
                    : m.pronostic_status === 'placed' ? '#D97706'
                    : '#555555'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '8px 0',
      borderBottom: '1px solid #2a2a2a',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '13px', color: '#CCCCCC' }}>{m.label}</span>
          {m.prediction_correct === true  && <CheckCircle size={13} color="#16A34A" />}
          {m.prediction_correct === false && <XCircle size={13} color="#DC2626" />}
        </div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '3px' }}>
          {ev && <span style={{ fontSize: '11px', color: '#16A34A' }}>{ev} EV</span>}
          {conf != null && <span style={{ fontSize: '11px', color: '#555' }}>conf. {conf}%</span>}
          {m.reference_odds && <span style={{ fontSize: '11px', color: '#555' }}>@ {formatCote(m.reference_odds)}</span>}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: '15px', fontWeight: '700', color: '#F5F5F5' }}>{pct}%</div>
        {m.pronostic_status && m.pronostic_status !== 'pending' && (
          <div style={{ fontSize: '10px', color: statusColor, fontWeight: '600', marginTop: '2px' }}>
            {m.pronostic_status === 'won'    ? 'GAGNÉ'
           : m.pronostic_status === 'lost'   ? 'PERDU'
           : m.pronostic_status === 'placed' ? 'MISÉ'
           : m.pronostic_status === 'void'   ? 'ANNULÉ'
           : m.pronostic_status.toUpperCase()}
          </div>
        )}
        {m.actual_profit != null && (
          <div style={{
            fontSize: '12px', fontWeight: '700',
            color: m.actual_profit >= 0 ? '#16A34A' : '#DC2626',
            marginTop: '1px',
          }}>
            {m.actual_profit >= 0 ? '+' : ''}{m.actual_profit.toFixed(2)}€
          </div>
        )}
      </div>
    </div>
  )
}

function MatchCard({ item }) {
  const [open, setOpen] = useState(false)

  const isPast = item.match_status === 'complete'
  const isLive = item.match_status === 'live'

  // Marché avec la plus haute confiance
  const best = item.markets.reduce((a, b) =>
    (b.confidence_score || 0) > (a.confidence_score || 0) ? b : a, item.markets[0])

  // Stats rapides : combien de marchés corrects / incorrects
  const corrects  = item.markets.filter(m => m.prediction_correct === true).length
  const incorrects = item.markets.filter(m => m.prediction_correct === false).length

  return (
    <div style={{
      backgroundColor: '#242424',
      borderRadius: '10px',
      border: `1px solid ${isLive ? '#D97706' : '#333333'}`,
      marginBottom: '8px',
      overflow: 'hidden',
    }}>
      {/* En-tête match */}
      <div onClick={() => setOpen(o => !o)} style={{ padding: '14px 16px', cursor: 'pointer' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Équipes */}
            <div style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5', marginBottom: '2px' }}>
              {item.home_team}
              {item.score
                ? <span style={{ margin: '0 6px', color: '#2563EB', fontWeight: '700' }}>{item.score}</span>
                : <span style={{ margin: '0 6px', color: '#444' }}>vs</span>
              }
              {item.away_team}
            </div>
            {/* Ligue + date */}
            <div style={{ fontSize: '11px', color: '#555', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <span>{item.league}</span>
              <span>·</span>
              <span>{formatDate(item.kickoff_timestamp)} {formatHeure(item.kickoff_timestamp)}</span>
              {isLive && <span style={{ color: '#D97706', fontWeight: '700' }}>● EN DIRECT</span>}
            </div>
          </div>

          {/* Côté droit : résumé + chevron */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0, marginLeft: '8px' }}>
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
              {isPast && corrects > 0 && (
                <span style={{ fontSize: '11px', color: '#16A34A', fontWeight: '600' }}>
                  {corrects}✓
                </span>
              )}
              {isPast && incorrects > 0 && (
                <span style={{ fontSize: '11px', color: '#DC2626', fontWeight: '600' }}>
                  {incorrects}✗
                </span>
              )}
              {!isPast && best && (
                <span style={{ fontSize: '12px', color: '#D97706' }}>
                  {Math.round((best.confidence_score || 0) * 100)}% conf.
                </span>
              )}
            </div>
            <span style={{ fontSize: '11px', color: '#555' }}>
              {item.markets.length} marché{item.markets.length > 1 ? 's' : ''}
            </span>
            {open
              ? <ChevronUp size={14} color="#555" />
              : <ChevronDown size={14} color="#555" />
            }
          </div>
        </div>
      </div>

      {/* Détail marchés */}
      {open && (
        <div style={{ borderTop: '1px solid #2a2a2a', padding: '4px 16px 12px' }}>
          {item.markets.map((m, i) => (
            <MarketRow key={i} m={m} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Analyse() {
  const [mode, setMode]     = useState('all')
  const [search, setSearch] = useState('')
  const [query, setQuery]   = useState('')   // query confirmée (après debounce)
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [page, setPage]     = useState(1)
  const debounceRef = useRef(null)

  const fetchData = useCallback(async (m, q, p) => {
    setLoading(true)
    setError(null)
    try {
      const params = { mode: m, page: p, limit: 20 }
      if (q) params.search = q
      const res = await api.get('/analyse/matches', { params })
      setData(res.data)
    } catch {
      setError("Impossible de charger les analyses")
    } finally {
      setLoading(false)
    }
  }, [])

  // Rechargement quand mode ou page change
  useEffect(() => {
    fetchData(mode, query, page)
  }, [mode, page, query, fetchData])

  // Debounce sur la recherche
  const handleSearch = (val) => {
    setSearch(val)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setQuery(val)
      setPage(1)
    }, 400)
  }

  const handleModeChange = (m) => {
    setMode(m)
    setPage(1)
  }

  const items = data?.items || []
  const pagination = data?.pagination

  return (
    <div style={{ padding: '16px', paddingBottom: '32px' }}>
      {/* En-tête */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingTop: '8px', marginBottom: '16px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>Analyse</h1>
          <p style={{ fontSize: '13px', color: '#666', marginTop: '2px' }}>Détail de toutes les prédictions</p>
        </div>
        <button onClick={() => fetchData(mode, query, page)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}>
          <RefreshCw size={18} color="#555" />
        </button>
      </div>

      {/* Barre de recherche */}
      <div style={{ position: 'relative', marginBottom: '12px' }}>
        <Search size={16} color="#555" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
        <input
          value={search}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Rechercher une équipe ou ligue…"
          style={{
            width: '100%',
            padding: '10px 36px 10px 36px',
            backgroundColor: '#242424',
            border: '1px solid #333',
            borderRadius: '10px',
            color: '#F5F5F5',
            fontSize: '13px',
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        {search && (
          <button
            onClick={() => handleSearch('')}
            style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
          >
            <X size={14} color="#555" />
          </button>
        )}
      </div>

      {/* Filtres */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px' }}>
        {MODES.map(m => (
          <button
            key={m.id}
            onClick={() => handleModeChange(m.id)}
            style={{
              padding: '7px 14px',
              borderRadius: '9999px',
              border: 'none',
              backgroundColor: mode === m.id ? '#2563EB' : '#242424',
              color: mode === m.id ? '#FFFFFF' : '#666666',
              fontSize: '13px',
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            {m.label}
            {pagination && m.id === 'all' && (
              <span style={{ marginLeft: '4px', color: mode === m.id ? '#AACCFF' : '#444' }}>
                {pagination.total}
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
        <div style={{ textAlign: 'center', padding: '32px', color: '#DC2626', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon={Search}
          title="Aucune analyse trouvée"
          message={
            query
              ? `Aucun résultat pour "${query}".`
              : mode === 'upcoming'
              ? "Aucun match à venir avec des prédictions."
              : mode === 'past'
              ? "Aucun match passé avec des prédictions pour l'instant."
              : "Les prédictions apparaîtront ici dès que le système en générera."
          }
        />
      )}

      {!loading && !error && items.map(item => (
        <MatchCard key={item.match_id} item={item} />
      ))}

      {/* Pagination */}
      {!loading && pagination && pagination.pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
          <button
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
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
            onClick={() => setPage(p => p + 1)}
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
