import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { TrendingUp, Clock, AlertCircle, Moon, ChevronRight, Zap } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'
import Skeleton from '../components/shared/Skeleton.jsx'
import EmptyState from '../components/shared/EmptyState.jsx'
import { formatEuros, formatCote, formatHeure, formatDate } from '../utils/formatters.js'

const mockData = {
  system_mode: 'active',
  pronostics: [
    {
      id: 1,
      match: {
        id: 1,
        home_team: 'PSG',
        away_team: 'Toulouse',
        league: 'Ligue 1',
        kickoff: '2026-04-03T18:45:00Z',
        kickoff_timestamp: 1743706500,
      },
      market: 'over25',
      market_label: 'Plus de 2.5 buts',
      reference_bookmaker: 'Pinnacle',
      reference_odds: 1.90,
      model_probability: 0.72,
      bookmaker_probability: 0.503,
      probability_edge: 0.217,
      expected_value: 0.368,
      confidence_score: 0.76,
      recommended_stake: 12.50,
      potential_gain: 23.75,
      movement_type: null,
      status: 'pending',
    },
    {
      id: 2,
      match: {
        id: 2,
        home_team: 'Real Sociedad',
        away_team: 'Levante',
        league: 'La Liga',
        kickoff: '2026-04-04T12:00:00Z',
        kickoff_timestamp: 1743768000,
      },
      market: 'over25',
      market_label: 'Plus de 2.5 buts',
      reference_bookmaker: 'Pinnacle',
      reference_odds: 1.75,
      model_probability: 0.74,
      bookmaker_probability: 0.571,
      probability_edge: 0.169,
      expected_value: 0.295,
      confidence_score: 0.74,
      recommended_stake: 10.00,
      potential_gain: 17.50,
      movement_type: null,
      status: 'pending',
    },
  ],
  combine_recommendation: null,
  bankroll_summary: {
    current: 150.00,
    today_change: 0,
    week_change: 0,
    week_change_pct: 0,
  }
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? '#16A34A' : pct >= 65 ? '#2563EB' : '#D97706'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{
        flex: 1,
        height: '4px',
        backgroundColor: '#333333',
        borderRadius: '9999px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          backgroundColor: color,
          borderRadius: '9999px',
          transition: 'width 0.5s ease',
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
      <div onClick={() => setExpanded(!expanded)}>
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

        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '8px',
          marginTop: '12px',
        }}>
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
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>Edge sur bookmaker</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#16A34A' }}>
              +{Math.round(pronostic.probability_edge * 100)}%
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>Référence</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#F5F5F5' }}>
              {pronostic.reference_bookmaker}
            </span>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', color: '#666666', marginBottom: '8px' }}>
              Mise recommandée
            </div>
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
                padding: '12px',
                borderRadius: '10px',
                border: '1px solid #444444',
                backgroundColor: 'transparent',
                color: '#A0A0A0',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer',
              }}
            >
              Ignorer
            </button>
            <button
              onClick={() => onPlace(pronostic.id, mise, pronostic.reference_odds)}
              style={{
                padding: '12px',
                borderRadius: '10px',
                border: 'none',
                backgroundColor: '#2563EB',
                color: '#FFFFFF',
                fontSize: '14px',
                fontWeight: '600',
                cursor: 'pointer',
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
  const [data, setData] = useState(mockData)
  const [loading, setLoading] = useState(false)

  const handlePlace = (id, stake, odds) => {
    alert(`Pari validé — Mise: ${stake}€ — Cote: ${odds}`)
  }

  const handleIgnore = (id) => {
    setData(prev => ({
      ...prev,
      pronostics: prev.pronostics.filter(p => p.id !== id)
    }))
  }

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
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '2px' }}>Bankroll</div>
          <div style={{ fontSize: '20px', fontWeight: '700', color: '#F5F5F5' }}>
            {data.bankroll_summary.current.toFixed(2)}€
          </div>
        </div>
      </div>

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
      ) : data.pronostics.length === 0 ? (
        <EmptyState
          icon={Moon}
          title="Aucune opportunité aujourd'hui"
          message="Le système surveille les matchs en continu. Les prochains pronostics arrivent le 3 avril."
        />
      ) : (
        <>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '16px',
          }}>
            <Zap size={14} color="#2563EB" />
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>
              {data.pronostics.length} opportunité{data.pronostics.length > 1 ? 's' : ''} identifiée{data.pronostics.length > 1 ? 's' : ''}
            </span>
          </div>

          {data.pronostics.map(p => (
            <PronosticCard
              key={p.id}
              pronostic={p}
              onPlace={handlePlace}
              onIgnore={handleIgnore}
            />
          ))}

          <Card style={{ marginTop: '8px', backgroundColor: '#1A2535' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertCircle size={16} color="#2563EB" />
              <span style={{ fontSize: '12px', color: '#A0A0A0', lineHeight: '1.5' }}>
                Trêve internationale jusqu'au 2 avril. Pronostics basés sur l'analyse Dixon-Coles.
              </span>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
