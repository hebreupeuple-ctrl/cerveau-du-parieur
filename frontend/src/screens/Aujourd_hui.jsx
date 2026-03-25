import React, { useEffect, useState } from 'react'
import { Moon, Zap, AlertCircle, RefreshCw } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'
import Skeleton from '../components/shared/Skeleton.jsx'
import EmptyState from '../components/shared/EmptyState.jsx'
import { formatCote, formatHeure, formatDate } from '../utils/formatters.js'
import api from '../services/api.js'

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? '#16A34A' : pct >= 65 ? '#2563EB' : '#D97706'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{
        flex: 1, height: '4px',
        backgroundColor: '#333333',
        borderRadius: '9999px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          backgroundColor: color,
          borderRadius: '9999px',
        }} />
      </div>
      <span style={{ fontSize: '12px', fontWeight: '600', color, minWidth: '32px' }}>
        {pct}%
      </span>
    </div>
  )
}

function PronosticCard({ pronostic, onPlace, onIgnore }) {
  const [expanded, setExpanded] = useState(false)
  const [mise, setMise] = useState(pronostic.recommended_stake)

  return (
    <Card style={{ marginBottom: '12px' }}>
      <div onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '3px' }}>
              {pronostic.match.home_team} vs {pronostic.match.away_team}
            </div>
            <div style={{ fontSize: '12px', color: '#666666' }}>
              {pronostic.match.league} · {formatDate(pronostic.match.kickoff_timestamp)} · {formatHeure(pronostic.match.kickoff_timestamp)}
            </div>
          </div>
          <Badge variant="accent">{pronostic.market_label}</Badge>
        </div>
        <ConfidenceBar value={pronostic.confidence_score} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginTop: '12px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: '#666666', marginBottom: '2px' }}>Cote</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#F5F5F5' }}>
              {formatCote(pronostic.reference_odds)}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: '#666666', marginBottom: '2px' }}>Notre prob.</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#2563EB' }}>
              {Math.round(pronostic.model_probability * 100)}%
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: '#666666', marginBottom: '2px' }}>Valeur</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#16A34A' }}>
              +{Math.round(pronostic.expected_value * 100)}%
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '16px', borderTop: '1px solid #333333', paddingTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>Edge bookmaker</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#16A34A' }}>
              +{Math.round((pronostic.probability_edge || 0) * 100)}%
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>Référence</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#F5F5F5' }}>
              {pronostic.reference_bookmaker}
            </span>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', color: '#666666', marginBottom: '8px' }}>Mise recommandée</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <input
                type="number"
                value={mise}
                onChange={(e) => setMise(parseFloat(e.target.value) || pronostic.recommended_stake)}
                min="5"
                step="0.5"
                style={{
                  flex: 1,
                  backgroundColor: '#1A1A1A',
                  border: '1px solid #444444',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  color: '#F5F5F5',
                  fontSize: '16px',
                  fontWeight: '600',
                  outline: 'none',
                }}
              />
              <div style={{ fontSize: '13px', color: '#A0A0A0' }}>
                Gain : <span style={{ color: '#16A34A', fontWeight: '600' }}>
                  {(mise * pronostic.reference_odds).toFixed(2)}€
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <button
              onClick={() => onIgnore(pronostic.id)}
              style={{
                padding: '12px', borderRadius: '10px',
                border: '1px solid #444444',
                backgroundColor: 'transparent',
                color: '#A0A0A0', fontSize: '14px',
                fontWeight: '500', cursor: 'pointer',
              }}
            >
              Ignorer
            </button>
            <button
              onClick={() => onPlace(pronostic.id, mise, pronostic.reference_odds)}
              style={{
                padding: '12px', borderRadius: '10px',
                border: 'none', backgroundColor: '#2563EB',
                color: '#FFFFFF', fontSize: '14px',
                fontWeight: '600', cursor: 'pointer',
              }}
            >
              Valider le pari
            </button>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Aujourd_hui() {
  const [data, setData] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [syncStatus, setSyncStatus] = useState(null)

  const charger = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      if (!token) {
        setError('Non connecté')
        setLoading(false)
        return
      }
      const [pronosticsRes, meRes] = await Promise.all([
        api.get('/pronostics/today'),
        api.get('/auth/me'),
      ])
      setData(pronosticsRes.data)
      setProfile(meRes.data)
    } catch (e) {
      setError('Erreur de connexion au serveur')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncStatus(null)

    try {
      const res = await api.post('/system/manual-sync', {}, { timeout: 60000 })
      const inserted = res.data?.pronostics_inserted ?? 0
      setSyncStatus({
        type: 'success',
        message: `Synchronisation terminée · ${inserted} pronostic${inserted > 1 ? 's' : ''} mis à jour`,
      })
      await charger()
    } catch (e) {
      setSyncStatus({
        type: 'error',
        message: e?.error?.message || e?.detail || 'Synchronisation impossible pour le moment',
      })
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    charger()
  }, [])

  const handlePlace = async (id, stake, odds) => {
    // Mise à jour optimiste de la bankroll avant la réponse serveur
    const bankrollAvant = data?.bankroll_summary?.current
    if (bankrollAvant != null) {
      setData(prev => ({
        ...prev,
        bankroll_summary: { ...prev.bankroll_summary, current: bankrollAvant - stake },
      }))
    }
    try {
      await api.post(`/pronostics/${id}/place`, {
        actual_stake: stake,
        actual_odds: odds,
      })
      charger()
    } catch (e) {
      // Rollback optimiste si l'API échoue
      if (bankrollAvant != null) {
        setData(prev => ({
          ...prev,
          bankroll_summary: { ...prev.bankroll_summary, current: bankrollAvant },
        }))
      }
      alert('Erreur lors de la validation du pari')
    }
  }

  const handleIgnore = async (id) => {
    try {
      await api.post(`/pronostics/${id}/ignore`, {})
      charger()
    } catch (e) {
      alert('Erreur')
    }
  }

  const pronostics = data?.pronostics || []
  const bankroll = data?.bankroll_summary?.current || 150
  const prochainMatch = data?.prochain_match

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingTop: '8px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>
            Aujourd'hui
          </h1>
          <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {profile?.is_admin && (
            <button
              onClick={handleSync}
              disabled={syncing}
              style={{
                padding: '8px 12px',
                borderRadius: '9999px',
                border: '1px solid #333333',
                backgroundColor: syncing ? '#1A1A1A' : '#242424',
                color: syncing ? '#666666' : '#A0A0A0',
                fontSize: '12px',
                fontWeight: '600',
                cursor: syncing ? 'not-allowed' : 'pointer',
              }}
            >
              {syncing ? 'Sync...' : 'Synchroniser'}
            </button>
          )}
          <button
            onClick={charger}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
          >
            <RefreshCw size={16} color="#666666" />
          </button>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11px', color: '#666666', marginBottom: '2px' }}>Bankroll</div>
            <div style={{ fontSize: '20px', fontWeight: '700', color: '#F5F5F5' }}>
              {bankroll.toFixed(2)}€
            </div>
          </div>
        </div>
      </div>

      {syncStatus && (
        <Card
          style={{
            marginBottom: '16px',
            padding: '12px 14px',
            backgroundColor: syncStatus.type === 'success' ? '#14261B' : '#2A1616',
            borderColor: syncStatus.type === 'success' ? '#1F5A35' : '#6B1F1F',
          }}
        >
          <p style={{
            fontSize: '12px',
            color: syncStatus.type === 'success' ? '#7DD3A6' : '#FCA5A5',
            lineHeight: '1.4',
          }}>
            {syncStatus.message}
          </p>
        </Card>
      )}

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[1, 2].map(i => (
            <Card key={i}>
              <Skeleton height="20px" style={{ marginBottom: '8px' }} />
              <Skeleton height="14px" width="60%" style={{ marginBottom: '16px' }} />
              <Skeleton height="4px" style={{ marginBottom: '12px' }} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                <Skeleton height="40px" />
                <Skeleton height="40px" />
                <Skeleton height="40px" />
              </div>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card style={{ textAlign: 'center', padding: '32px 16px' }}>
          <AlertCircle size={32} color="#DC2626" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: '#DC2626', fontSize: '14px', marginBottom: '16px' }}>{error}</p>
          <button
            onClick={charger}
            style={{
              padding: '10px 20px', borderRadius: '8px',
              border: 'none', backgroundColor: '#2563EB',
              color: '#FFFFFF', cursor: 'pointer', fontSize: '14px',
            }}
          >
            Réessayer
          </button>
        </Card>
      ) : pronostics.length === 0 ? (
        <>
          <EmptyState
            icon={Moon}
            title="Aucun match aujourd'hui"
            message="Pas de match de nos ligues suivies pour le moment."
          />
          {prochainMatch && (
            <Card style={{ marginTop: '16px', backgroundColor: '#1A2535' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <AlertCircle size={16} color="#2563EB" style={{ marginTop: '1px', flexShrink: 0 }} />
                <div>
                  <p style={{ fontSize: '13px', color: '#A0A0A0', lineHeight: '1.5' }}>
                    Le système surveille en continu les prochains matchs.
                  </p>
                  <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
                    Prochain match : {prochainMatch.home} vs {prochainMatch.away} le{' '}
                    {new Date(prochainMatch.timestamp * 1000).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}
                  </p>
                </div>
              </div>
            </Card>
          )}
        </>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '16px' }}>
            <Zap size={14} color="#2563EB" />
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>
              {pronostics.length} opportunité{pronostics.length > 1 ? 's' : ''} identifiée{pronostics.length > 1 ? 's' : ''}
            </span>
          </div>
          {pronostics.map(p => (
            <PronosticCard
              key={p.id}
              pronostic={p}
              onPlace={handlePlace}
              onIgnore={handleIgnore}
            />
          ))}
        </>
      )}
    </div>
  )
}
