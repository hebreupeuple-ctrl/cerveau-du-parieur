import React, { useState } from 'react'
import { TrendingUp, TrendingDown, Target, Award, BarChart2, AlertTriangle } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'

const mockPerf = {
  metrics: {
    roi: 0.083,
    avg_clv: 0.041,
    max_drawdown: -0.112,
    win_rate: 0.68,
  },
  volume: {
    total_bets: 0,
    bets_won: 0,
    bets_lost: 0,
    total_staked: 0,
    total_profit: 0,
  },
  bankroll: {
    initial: 150.00,
    current: 150.00,
  },
  by_market: [
    { market: 'over25', market_label: 'Over 2.5', bets: 0, roi: null, is_active: true },
    { market: 'btts', market_label: 'BTTS', bets: 0, roi: null, is_active: true },
  ],
  model_health: {
    brier_score: 0.2487,
    auc_roc: 0.5776,
    last_retrain: '2026-03-24',
    model_version: '2026.03.v1',
    bias_alerts: [],
  }
}

function MetricCard({ label, value, sub, icon: Icon, color = '#F5F5F5', positive }) {
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
  const data = mockPerf

  const periods = [
    { id: 'week', label: 'Semaine' },
    { id: 'month', label: 'Mois' },
    { id: 'all', label: 'Total' },
  ]

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ paddingTop: '8px', marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>
          Performance
        </h1>
        <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>
          Suivi de vos résultats
        </p>
      </div>

      <div style={{ display: 'flex', gap: '6px', marginBottom: '20px' }}>
        {periods.map(p => (
          <button
            key={p.id}
            onClick={() => setPeriod(p.id)}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: period === p.id ? '#2563EB' : '#242424',
              color: period === p.id ? '#FFFFFF' : '#666666',
              fontSize: '13px',
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
        <MetricCard
          label="ROI Global"
          value={data.volume.total_bets === 0 ? '—' : `+${(data.metrics.roi * 100).toFixed(1)}%`}
          sub="Retour sur investissement"
          icon={TrendingUp}
          color={data.metrics.roi >= 0 ? '#16A34A' : '#DC2626'}
        />
        <MetricCard
          label="CLV Moyen"
          value={data.volume.total_bets === 0 ? '—' : `+${(data.metrics.avg_clv * 100).toFixed(1)}%`}
          sub="Closing Line Value"
          icon={Target}
          color="#2563EB"
        />
        <MetricCard
          label="Drawdown Max"
          value={data.volume.total_bets === 0 ? '—' : `${(data.metrics.max_drawdown * 100).toFixed(1)}%`}
          sub="Perte maximale"
          icon={TrendingDown}
          color="#DC2626"
        />
        <MetricCard
          label="Paris joués"
          value={data.volume.total_bets}
          sub={`${data.volume.bets_won}G / ${data.volume.bets_lost}P`}
          icon={BarChart2}
          color="#F5F5F5"
        />
      </div>

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <span style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5' }}>
            Bankroll
          </span>
          <Badge variant="muted">Départ : {data.bankroll.initial.toFixed(2)}€</Badge>
        </div>
        <div style={{ fontSize: '32px', fontWeight: '700', color: '#F5F5F5', marginBottom: '4px' }}>
          {data.bankroll.current.toFixed(2)}€
        </div>
        <div style={{ fontSize: '13px', color: '#666666' }}>
          {data.volume.total_bets === 0
            ? 'Aucun pari encore placé'
            : `${data.volume.total_profit >= 0 ? '+' : ''}${data.volume.total_profit.toFixed(2)}€ de profit`
          }
        </div>

        <div style={{
          marginTop: '20px',
          height: '80px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#1A1A1A',
          borderRadius: '8px',
          border: '1px dashed #333333',
        }}>
          <span style={{ fontSize: '12px', color: '#444444' }}>
            Graphique disponible après les premiers paris
          </span>
        </div>
      </Card>

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '16px' }}>
          Santé du modèle
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {[
            { label: 'Brier Score', value: data.model_health.brier_score.toFixed(4), status: data.model_health.brier_score < 0.25 ? 'Excellent' : 'Bon', color: '#16A34A' },
            { label: 'AUC-ROC', value: data.model_health.auc_roc.toFixed(4), status: data.model_health.auc_roc > 0.60 ? 'Bon' : 'Correct', color: '#2563EB' },
            { label: 'Version modèle', value: data.model_health.model_version, status: null, color: '#F5F5F5' },
            { label: 'Dernier entraînement', value: data.model_health.last_retrain, status: null, color: '#F5F5F5' },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: '600', color: item.color }}>
                  {item.value}
                </span>
                {item.status && (
                  <Badge variant="success" style={{ fontSize: '10px' }}>{item.status}</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5', marginBottom: '16px' }}>
          Par marché
        </div>
        {data.by_market.map(m => (
          <div key={m.market} style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            paddingBottom: '12px',
            marginBottom: '12px',
            borderBottom: '1px solid #2E2E2E',
          }}>
            <div>
              <div style={{ fontSize: '14px', fontWeight: '500', color: '#F5F5F5' }}>
                {m.market_label}
              </div>
              <div style={{ fontSize: '12px', color: '#666666', marginTop: '2px' }}>
                {m.bets} paris
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '15px', fontWeight: '700', color: m.roi === null ? '#666666' : m.roi >= 0 ? '#16A34A' : '#DC2626' }}>
                {m.roi === null ? '—' : `${m.roi >= 0 ? '+' : ''}${(m.roi * 100).toFixed(1)}%`}
              </div>
              <Badge variant={m.is_active ? 'success' : 'danger'} style={{ fontSize: '10px', marginTop: '4px' }}>
                {m.is_active ? 'Actif' : 'Inactif'}
              </Badge>
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}
