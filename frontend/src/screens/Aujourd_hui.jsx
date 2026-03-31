import React, { useEffect, useState } from 'react'
import { Moon, Zap, AlertCircle, RefreshCw, Shield, TrendingUp, Crosshair, ChevronDown, ChevronUp } from 'lucide-react'
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
      <div style={{ flex: 1, height: '4px', backgroundColor: '#333', borderRadius: '9999px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', backgroundColor: color, borderRadius: '9999px' }} />
      </div>
      <span style={{ fontSize: '12px', fontWeight: '600', color, minWidth: '32px' }}>{pct}%</span>
    </div>
  )
}

function PronosticRow({ pronostic, role, onPlace, onIgnore }) {
  const [mise, setMise] = useState(pronostic.recommended_stake)
  const [expanded, setExpanded] = useState(false)

  const roleConfig = {
    safe:      { label: 'SAFE',      icon: Shield,     color: '#16A34A', bg: '#14261B', border: '#1F5A35' },
    valeur:    { label: 'VALEUR',    icon: TrendingUp, color: '#2563EB', bg: '#1A2535', border: '#1E3A5F' },
    precision: { label: 'PRÉCISION', icon: Crosshair,  color: '#D97706', bg: '#261E14', border: '#5A3A1F' },
  }
  const cfg = roleConfig[role] || roleConfig.safe
  const Icon = cfg.icon

  return (
    <div style={{
      backgroundColor: cfg.bg,
      border: `1px solid ${cfg.border}`,
      borderRadius: '10px',
      padding: '12px',
      marginBottom: '8px',
    }}>
      {/* En-tête rôle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Icon size={13} color={cfg.color} />
          <span style={{ fontSize: '11px', fontWeight: '700', color: cfg.color, letterSpacing: '0.5px' }}>
            {cfg.label}
          </span>
        </div>
        <Badge variant="accent" style={{ fontSize: '11px' }}>{pronostic.market_label}</Badge>
      </div>

      {/* Stats clés */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '10px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '10px', color: '#666', marginBottom: '2px' }}>Cote</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#F5F5F5' }}>{formatCote(pronostic.reference_odds)}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '10px', color: '#666', marginBottom: '2px' }}>Prob. modèle</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#2563EB' }}>
            {Math.round(pronostic.model_probability * 100)}%
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '10px', color: '#666', marginBottom: '2px' }}>Valeur</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#16A34A' }}>
            +{Math.round(pronostic.expected_value * 100)}%
          </div>
        </div>
      </div>

      <ConfidenceBar value={pronostic.confidence_score} />

      {/* Toggle détails */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', cursor: 'pointer' }}
      >
        {expanded
          ? <ChevronUp size={16} color="#555" />
          : <ChevronDown size={16} color="#555" />
        }
      </div>

      {expanded && (
        <div style={{ marginTop: '10px', borderTop: '1px solid #333', paddingTop: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', color: '#A0A0A0' }}>Edge bookmaker</span>
            <span style={{ fontSize: '12px', fontWeight: '600', color: '#16A34A' }}>
              +{Math.round((pronostic.probability_edge || 0) * 100)}%
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
            <span style={{ fontSize: '12px', color: '#A0A0A0' }}>Mise recommandée</span>
            <span style={{ fontSize: '12px', fontWeight: '600', color: '#F5F5F5' }}>
              {pronostic.recommended_stake?.toFixed(2)}€
            </span>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '6px' }}>Ajuster la mise</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="number"
                value={mise}
                onChange={e => setMise(parseFloat(e.target.value) || pronostic.recommended_stake)}
                min="5" step="0.5"
                style={{
                  flex: 1, backgroundColor: '#1A1A1A', border: '1px solid #444',
                  borderRadius: '8px', padding: '8px 10px', color: '#F5F5F5',
                  fontSize: '15px', fontWeight: '600', outline: 'none',
                }}
              />
              <div style={{ fontSize: '12px', color: '#A0A0A0' }}>
                Gain : <span style={{ color: '#16A34A', fontWeight: '600' }}>
                  +{(mise * (pronostic.reference_odds - 1)).toFixed(2)}€
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <button
              onClick={() => onIgnore(pronostic.id)}
              style={{
                padding: '10px', borderRadius: '8px', border: '1px solid #444',
                backgroundColor: 'transparent', color: '#A0A0A0',
                fontSize: '13px', fontWeight: '500', cursor: 'pointer',
              }}
            >
              Ignorer
            </button>
            <button
              onClick={() => onPlace(pronostic.id, mise, pronostic.reference_odds)}
              style={{
                padding: '10px', borderRadius: '8px', border: 'none',
                backgroundColor: '#2563EB', color: '#FFF',
                fontSize: '13px', fontWeight: '600', cursor: 'pointer',
              }}
            >
              Valider le pari
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function FicheMatch({ fiche, onPlace, onIgnore }) {
  const { match, safe, valeur, precision, exact_scores } = fiche
  const [showAll, setShowAll] = useState(false)
  const allPronos = fiche.all || []
  const shownByRole = new Set([safe?.id, valeur?.id, precision?.id].filter(Boolean))
  const extras = allPronos.filter(p => !shownByRole.has(p.id))

  return (
    <Card style={{ marginBottom: '16px', padding: '0', overflow: 'hidden' }}>
      {/* En-tête match */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid #2E2E2E',
        backgroundColor: '#1A1A1A',
      }}>
        <div style={{ fontSize: '15px', fontWeight: '700', color: '#F5F5F5' }}>
          {match.home_team} <span style={{ color: '#555', fontWeight: '400' }}>vs</span> {match.away_team}
        </div>
        <div style={{ fontSize: '12px', color: '#666', marginTop: '3px' }}>
          {match.league} · {formatDate(match.kickoff_timestamp)} · {formatHeure(match.kickoff_timestamp)}
        </div>
      </div>

      <div style={{ padding: '12px' }}>
        {/* SAFE */}
        {safe && <PronosticRow pronostic={safe} role="safe" onPlace={onPlace} onIgnore={onIgnore} />}
        {/* VALEUR */}
        {valeur && <PronosticRow pronostic={valeur} role="valeur" onPlace={onPlace} onIgnore={onIgnore} />}
        {/* PRÉCISION */}
        {precision && <PronosticRow pronostic={precision} role="precision" onPlace={onPlace} onIgnore={onIgnore} />}

        {/* Scores exacts */}
        {exact_scores?.length > 0 && (
          <div style={{
            marginTop: '4px', padding: '10px 12px',
            backgroundColor: '#1A1A1A', borderRadius: '8px',
            border: '1px solid #2E2E2E',
          }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px', fontWeight: '600', letterSpacing: '0.5px' }}>
              SCORES LES PLUS PROBABLES
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {exact_scores.map((s, i) => (
                <div key={i} style={{
                  backgroundColor: '#242424', borderRadius: '6px',
                  padding: '6px 10px', textAlign: 'center',
                  border: i === 0 ? '1px solid #444' : '1px solid #2E2E2E',
                }}>
                  <div style={{ fontSize: '16px', fontWeight: '700', color: i === 0 ? '#F5F5F5' : '#A0A0A0' }}>
                    {s.score}
                  </div>
                  <div style={{ fontSize: '10px', color: '#555', marginTop: '2px' }}>{s.probabilite}%</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Autres pronostics */}
        {extras.length > 0 && (
          <div style={{ marginTop: '8px' }}>
            <button
              onClick={() => setShowAll(!showAll)}
              style={{
                width: '100%', padding: '8px', background: 'none',
                border: '1px solid #2E2E2E', borderRadius: '8px',
                color: '#666', fontSize: '12px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              }}
            >
              {showAll ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {showAll ? 'Masquer' : `${extras.length} autre${extras.length > 1 ? 's' : ''} opportunité${extras.length > 1 ? 's' : ''}`}
            </button>
            {showAll && extras.map(p => (
              <div key={p.id} style={{ marginTop: '8px' }}>
                <PronosticRow pronostic={p} role="valeur" onPlace={onPlace} onIgnore={onIgnore} />
              </div>
            ))}
          </div>
        )}
      </div>
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
  const [actionError, setActionError] = useState(null)
  const [generating, setGenerating] = useState(false)

  const charger = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      if (!token) { setError('Non connecté'); setLoading(false); return }
      const [pronosticsRes, meRes] = await Promise.all([
        api.get('/pronostics/today'),
        api.get('/auth/me'),
      ])
      setData(pronosticsRes.data)
      setProfile(meRes.data)
      if (pronosticsRes.data?.generating) {
        setGenerating(true)
        setTimeout(() => { setGenerating(false); charger() }, 4000)
      } else {
        setGenerating(false)
      }
    } catch {
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
      setSyncStatus({ type: 'success', message: `Synchronisation terminée · ${inserted} pronostic${inserted > 1 ? 's' : ''} mis à jour` })
      await charger()
    } catch (e) {
      setSyncStatus({ type: 'error', message: e?.error?.message || 'Synchronisation impossible pour le moment' })
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => { charger() }, [])

  const handlePlace = async (id, stake, odds) => {
    setActionError(null)
    const bankrollAvant = data?.bankroll_summary?.current
    if (bankrollAvant != null) {
      setData(prev => ({ ...prev, bankroll_summary: { ...prev.bankroll_summary, current: bankrollAvant - stake } }))
    }
    try {
      await api.post(`/pronostics/${id}/place`, { actual_stake: stake, actual_odds: odds })
      charger()
    } catch (e) {
      if (bankrollAvant != null) {
        setData(prev => ({ ...prev, bankroll_summary: { ...prev.bankroll_summary, current: bankrollAvant } }))
      }
      setActionError(e?.error?.message || 'Impossible de valider le pari')
    }
  }

  const handleIgnore = async (id) => {
    setActionError(null)
    try {
      await api.post(`/pronostics/${id}/ignore`, {})
      charger()
    } catch (e) {
      setActionError(e?.error?.message || 'Impossible d\'ignorer ce pronostic')
    }
  }

  const fiches = data?.fiches || []
  const bankroll = data?.bankroll_summary?.current ?? 150
  const todayChange = data?.bankroll_summary?.today_change ?? 0
  const weekChange = data?.bankroll_summary?.week_change ?? 0
  const prochainMatch = data?.prochain_match
  const totalOpportunites = fiches.reduce((acc, f) => acc + (f.all?.length || 0), 0)

  return (
    <div style={{ padding: '16px' }}>
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
      {/* En-tête */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingTop: '8px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>Aujourd'hui</h1>
          <p style={{ fontSize: '13px', color: '#666', marginTop: '2px' }}>
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {profile?.is_admin && (
            <button
              onClick={handleSync} disabled={syncing}
              style={{
                padding: '8px 12px', borderRadius: '9999px',
                border: '1px solid #333', backgroundColor: syncing ? '#1A1A1A' : '#242424',
                color: syncing ? '#666' : '#A0A0A0', fontSize: '12px', fontWeight: '600',
                cursor: syncing ? 'not-allowed' : 'pointer',
              }}
            >
              {syncing ? 'Sync...' : 'Synchroniser'}
            </button>
          )}
          <button onClick={charger} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}>
            <RefreshCw size={16} color="#666" />
          </button>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '2px' }}>Bankroll</div>
            <div style={{ fontSize: '20px', fontWeight: '700', color: '#F5F5F5' }}>{bankroll.toFixed(2)}€</div>
            <div style={{ fontSize: '11px', color: todayChange >= 0 ? '#16A34A' : '#DC2626' }}>
              {todayChange >= 0 ? '+' : ''}{todayChange.toFixed(2)}€ auj.
            </div>
            <div style={{ fontSize: '11px', color: weekChange >= 0 ? '#16A34A' : '#DC2626' }}>
              {weekChange >= 0 ? '+' : ''}{weekChange.toFixed(2)}€ semaine
            </div>
          </div>
        </div>
      </div>

      {actionError && (
        <Card style={{ marginBottom: '16px', padding: '12px 14px', backgroundColor: '#2A1616', borderColor: '#6B1F1F' }}>
          <p style={{ fontSize: '12px', color: '#FCA5A5' }}>{actionError}</p>
        </Card>
      )}

      {syncStatus && (
        <Card style={{
          marginBottom: '16px', padding: '12px 14px',
          backgroundColor: syncStatus.type === 'success' ? '#14261B' : '#2A1616',
          borderColor: syncStatus.type === 'success' ? '#1F5A35' : '#6B1F1F',
        }}>
          <p style={{ fontSize: '12px', color: syncStatus.type === 'success' ? '#7DD3A6' : '#FCA5A5' }}>
            {syncStatus.message}
          </p>
        </Card>
      )}

      {generating && (
        <Card style={{ marginBottom: '16px', padding: '12px 14px', backgroundColor: '#1A2535', borderColor: '#1E3A5F' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RefreshCw size={14} color="#2563EB" style={{ animation: 'spin 1s linear infinite' }} />
            <p style={{ fontSize: '12px', color: '#60A5FA' }}>Génération des pronostics en cours…</p>
          </div>
        </Card>
      )}

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {[1, 2].map(i => (
            <Card key={i}>
              <Skeleton height="16px" width="60%" style={{ marginBottom: '12px' }} />
              <Skeleton height="80px" style={{ marginBottom: '8px' }} />
              <Skeleton height="80px" style={{ marginBottom: '8px' }} />
              <Skeleton height="80px" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card style={{ textAlign: 'center', padding: '32px 16px' }}>
          <AlertCircle size={32} color="#DC2626" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: '#DC2626', fontSize: '14px', marginBottom: '16px' }}>{error}</p>
          <button onClick={charger} style={{ padding: '10px 20px', borderRadius: '8px', border: 'none', backgroundColor: '#2563EB', color: '#FFF', cursor: 'pointer', fontSize: '14px' }}>
            Réessayer
          </button>
        </Card>
      ) : fiches.length === 0 ? (
        <>
          <EmptyState icon={Moon} title="Aucun match aujourd'hui" message="Pas de match de nos ligues suivies pour le moment." />
          {prochainMatch && (
            <Card style={{ marginTop: '16px', backgroundColor: '#1A2535' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <AlertCircle size={16} color="#2563EB" style={{ marginTop: '1px', flexShrink: 0 }} />
                <div>
                  <p style={{ fontSize: '13px', color: '#A0A0A0', lineHeight: '1.5' }}>
                    Le système surveille en continu les prochains matchs.
                  </p>
                  <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                    Prochain : {prochainMatch.home} vs {prochainMatch.away} le{' '}
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
              {fiches.length} match{fiches.length > 1 ? 's' : ''} · {totalOpportunites} opportunité{totalOpportunites > 1 ? 's' : ''}
            </span>
          </div>
          {fiches.map((fiche, i) => (
            <FicheMatch
              key={fiche.match.id ?? i}
              fiche={fiche}
              onPlace={handlePlace}
              onIgnore={handleIgnore}
            />
          ))}
        </>
      )}
    </div>
  )
}
