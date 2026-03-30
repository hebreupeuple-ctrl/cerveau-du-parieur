import React, { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Target, Award, BarChart2, AlertTriangle, RefreshCw } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'
import Skeleton from '../components/shared/Skeleton.jsx'
import api from '../services/api.js'

function MetricCard({ label, value, sub, icon: Icon, color = '#F5F5F5' }) {
  return (
    <Card style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <span style={{ fontSize: '11px', color: '#666666', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {label}
        </span>
        {Icon && <Icon size={14} color="#444444" />}
      </div>
      <div style={{ fontSize: '22px', fontWeight: '700', color }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '11px', color: '#666666', marginTop: '4px' }}>
          {sub}
        </div>
      )}
    </Card>
  )
}

export default function Performance() {
  const [period, setPeriod] = useState('all')
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const charger = useCallback(async (p = period) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/performance/summary', { params: { period: p } })
      setData(res.data)
    } catch {
      setError('Impossible de charger les performances')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    charger(period)
  }, [period])

  const handlePeriod = (p) => {
    setPeriod(p)
  }

  const periods = [
    { id: 'week',  label: 'Semaine' },
    { id: 'month', label: 'Mois' },
    { id: 'all',   label: 'Total' },
  ]

  const fmt = (v, suffix = '%', decimals = 1) =>
    v == null ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(decimals)}${suffix}`

  const vol   = data?.volume   || {}
  const metr  = data?.metrics  || {}
  const bank  = data?.bankroll || {}
  const model = data?.model_health || {}

  const noParis = !vol.total_bets

  return (
    <div style={{ padding: '16px', paddingBottom: '32px' }}>
      {/* En-tête */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingTop: '8px', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>Performance</h1>
          <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>Suivi de vos résultats</p>
        </div>
        <button onClick={() => charger(period)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}>
          <RefreshCw size={18} color="#555" />
        </button>
      </div>

      {/* Filtres période */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '20px' }}>
        {periods.map(p => (
          <button
            key={p.id}
            onClick={() => handlePeriod(p.id)}
            style={{
              flex: 1, padding: '8px', borderRadius: '8px', border: 'none',
              backgroundColor: period === p.id ? '#2563EB' : '#242424',
              color: period === p.id ? '#FFFFFF' : '#666666',
              fontSize: '13px', fontWeight: '500', cursor: 'pointer',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            {[1,2,3,4].map(i => <Skeleton key={i} height={80} style={{ borderRadius: '10px' }} />)}
          </div>
          <Skeleton height={140} style={{ borderRadius: '10px' }} />
          <Skeleton height={180} style={{ borderRadius: '10px' }} />
        </div>
      ) : error ? (
        <Card style={{ textAlign: 'center', padding: '32px 16px' }}>
          <AlertTriangle size={28} color="#DC2626" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: '#DC2626', fontSize: '13px' }}>{error}</p>
        </Card>
      ) : (
        <>
          {/* Métriques */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
            <MetricCard
              label="ROI Global"
              value={noParis ? '—' : fmt(metr.roi)}
              sub="Retour sur investissement"
              icon={TrendingUp}
              color={metr.roi == null ? '#666' : metr.roi >= 0 ? '#16A34A' : '#DC2626'}
            />
            <MetricCard
              label="Win Rate"
              value={noParis ? '—' : metr.win_rate == null ? '—' : `${(metr.win_rate * 100).toFixed(0)}%`}
              sub={noParis ? '—' : `${vol.bets_won ?? 0}G / ${vol.bets_lost ?? 0}P`}
              icon={Target}
              color="#2563EB"
            />
            <MetricCard
              label="Profit net"
              value={noParis ? '—' : `${vol.total_profit >= 0 ? '+' : ''}${(vol.total_profit || 0).toFixed(2)}€`}
              sub={`${(vol.total_staked || 0).toFixed(2)}€ misés`}
              icon={BarChart2}
              color={vol.total_profit >= 0 ? '#16A34A' : '#DC2626'}
            />
            <MetricCard
              label="Paris joués"
              value={vol.total_bets ?? 0}
              sub={noParis ? 'Aucun pari encore' : `dont ${vol.bets_void ?? 0} annulé(s)`}
              icon={Award}
              color="#F5F5F5"
            />
          </div>

          {/* Bankroll */}
          <Card style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5' }}>Bankroll</span>
              <Badge variant="muted">Départ : {(bank.initial || 0).toFixed(2)}€</Badge>
            </div>
            <div style={{ fontSize: '32px', fontWeight: '700', color: '#F5F5F5', marginBottom: '4px' }}>
              {(bank.current || 0).toFixed(2)}€
            </div>
            <div style={{ fontSize: '13px', color: bank.current >= bank.initial ? '#16A34A' : '#DC2626' }}>
              {bank.current == null || bank.initial == null
                ? ''
                : `${bank.current - bank.initial >= 0 ? '+' : ''}${(bank.current - bank.initial).toFixed(2)}€ depuis le départ`
              }
            </div>
            <div style={{
              marginTop: '20px', height: '80px', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              backgroundColor: '#1A1A1A', borderRadius: '8px', border: '1px dashed #333333',
            }}>
              <span style={{ fontSize: '12px', color: '#444444' }}>
                Graphique disponible après les premiers paris
              </span>
            </div>
          </Card>

          {/* Santé du modèle */}
          <Card style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '16px' }}>
              Santé du modèle
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                {
                  label: 'Brier Score',
                  value: model.brier_score != null ? model.brier_score.toFixed(4) : '—',
                  status: model.brier_score != null ? (model.brier_score < 0.25 ? 'Excellent' : 'Bon') : null,
                  color: '#16A34A',
                },
                {
                  label: 'AUC-ROC',
                  value: model.auc_roc != null ? model.auc_roc.toFixed(4) : '—',
                  status: model.auc_roc != null ? (model.auc_roc > 0.60 ? 'Bon' : 'Correct') : null,
                  color: '#2563EB',
                },
                {
                  label: 'Matchs entraînement',
                  value: model.total_matches_trained ?? '—',
                  status: null,
                  color: '#F5F5F5',
                },
                {
                  label: 'Version modèle',
                  value: model.model_version ?? '—',
                  status: null,
                  color: '#F5F5F5',
                },
                {
                  label: 'Dernier entraînement',
                  value: model.last_retrain ? new Date(model.last_retrain).toLocaleDateString('fr-FR') : '—',
                  status: null,
                  color: '#F5F5F5',
                },
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13px', fontWeight: '600', color: item.color }}>{item.value}</span>
                    {item.status && <Badge variant="success" style={{ fontSize: '10px' }}>{item.status}</Badge>}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* CLV moyen */}
          {metr.avg_clv != null && (
            <Card style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '13px', color: '#A0A0A0' }}>Closing Line Value moyen</div>
                  <div style={{ fontSize: '11px', color: '#555555', marginTop: '2px' }}>
                    Sur {metr.clv_sample_size} pari{metr.clv_sample_size > 1 ? 's' : ''} · positif = edge réel confirmé
                  </div>
                </div>
                <div style={{
                  fontSize: '22px', fontWeight: '700',
                  color: metr.avg_clv >= 0 ? '#16A34A' : '#DC2626',
                }}>
                  {metr.avg_clv >= 0 ? '+' : ''}{metr.avg_clv.toFixed(2)}%
                </div>
              </div>
            </Card>
          )}

          {/* Par marché */}
          {data?.by_market?.length > 0 && (
            <Card style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '16px' }}>
                Par marché
              </div>
              {data.by_market.map((m, i) => (
                <div key={m.market} style={{
                  paddingBottom: '12px', marginBottom: '12px',
                  borderBottom: i < data.by_market.length - 1 ? '1px solid #2E2E2E' : 'none',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: '500', color: '#F5F5F5' }}>{m.market}</div>
                      <div style={{ fontSize: '12px', color: '#666666', marginTop: '2px' }}>
                        {m.total} paris · {m.won}G {m.lost}P · {(m.win_rate * 100).toFixed(0)}% win
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '15px', fontWeight: '700', color: m.roi == null ? '#666666' : m.roi >= 0 ? '#16A34A' : '#DC2626' }}>
                        {m.roi == null ? '—' : `${m.roi >= 0 ? '+' : ''}${(m.roi * 100).toFixed(1)}%`}
                      </div>
                      {m.avg_clv != null && (
                        <div style={{ fontSize: '11px', color: m.avg_clv >= 0 ? '#16A34A' : '#DC2626', marginTop: '2px' }}>
                          CLV {m.avg_clv >= 0 ? '+' : ''}{m.avg_clv.toFixed(1)}%
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </Card>
          )}

          {/* Par ligue */}
          {data?.by_league?.length > 0 && (
            <Card>
              <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '16px' }}>
                Par ligue
              </div>
              {data.by_league.map((l, i) => (
                <div key={l.league} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  paddingBottom: '12px', marginBottom: '12px',
                  borderBottom: i < data.by_league.length - 1 ? '1px solid #2E2E2E' : 'none',
                }}>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: '500', color: '#F5F5F5' }}>{l.league}</div>
                    <div style={{ fontSize: '12px', color: '#666666', marginTop: '2px' }}>
                      {l.total} paris · {l.won}G {l.lost}P
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '15px', fontWeight: '700', color: l.roi == null ? '#666666' : l.roi >= 0 ? '#16A34A' : '#DC2626' }}>
                      {l.roi == null ? '—' : `${l.roi >= 0 ? '+' : ''}${(l.roi * 100).toFixed(1)}%`}
                    </div>
                    <div style={{ fontSize: '11px', color: '#555555', marginTop: '2px' }}>
                      {l.profit >= 0 ? '+' : ''}{(l.profit || 0).toFixed(2)}€
                    </div>
                  </div>
                </div>
              ))}
            </Card>
          )}
        </>
      )}
    </div>
  )
}
