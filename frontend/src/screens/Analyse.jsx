import React, { useState } from 'react'
import { Search, ChevronDown } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'

const mockMatchs = [
  {
    id: 1,
    home_team: 'PSG',
    away_team: 'Toulouse',
    league: 'Ligue 1',
    kickoff_timestamp: 1743706500,
    has_pronostic: true,
    best_market: 'over25',
    best_confidence: 0.76,
    pred: {
      prob_home_win: 0.640,
      prob_draw: 0.227,
      prob_away_win: 0.132,
      prob_over25: 0.496,
      prob_btts: 0.456,
      most_likely_score: '1-0',
      dc_lambda: 1.9544,
      dc_mu: 0.7538,
    }
  },
  {
    id: 2,
    home_team: 'Real Sociedad',
    away_team: 'Levante',
    league: 'La Liga',
    kickoff_timestamp: 1743768000,
    has_pronostic: true,
    best_market: 'over25',
    best_confidence: 0.74,
    pred: {
      prob_home_win: 0.714,
      prob_draw: 0.163,
      prob_away_win: 0.123,
      prob_over25: 0.748,
      prob_btts: 0.639,
      most_likely_score: '2-1',
      dc_lambda: 2.1,
      dc_mu: 1.3,
    }
  },
  {
    id: 3,
    home_team: 'Freiburg',
    away_team: 'Bayern München',
    league: 'Bundesliga',
    kickoff_timestamp: 1743771000,
    has_pronostic: false,
    best_market: null,
    best_confidence: null,
    pred: {
      prob_home_win: 0.151,
      prob_draw: 0.262,
      prob_away_win: 0.587,
      prob_over25: 0.406,
      prob_btts: 0.409,
      most_likely_score: '0-1',
      dc_lambda: 0.8,
      dc_mu: 1.9,
    }
  },
]

function ProbBar({ label, value, color = '#2563EB' }) {
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '12px', color: '#A0A0A0' }}>{label}</span>
        <span style={{ fontSize: '12px', fontWeight: '600', color }}>
          {Math.round(value * 100)}%
        </span>
      </div>
      <div style={{ height: '4px', backgroundColor: '#333333', borderRadius: '9999px', overflow: 'hidden' }}>
        <div style={{
          width: `${value * 100}%`,
          height: '100%',
          backgroundColor: color,
          borderRadius: '9999px',
        }} />
      </div>
    </div>
  )
}

function MatchAnalyse({ match }) {
  const [open, setOpen] = useState(false)

  return (
    <Card style={{ marginBottom: '10px' }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: '15px', fontWeight: '600', color: '#F5F5F5' }}>
              {match.home_team} vs {match.away_team}
            </div>
            <div style={{ fontSize: '12px', color: '#666666', marginTop: '2px' }}>
              {match.league}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {match.has_pronostic && (
              <Badge variant="success">Pronostic</Badge>
            )}
            <ChevronDown
              size={16}
              color="#666666"
              style={{ transform: open ? 'rotate(180deg)' : 'none', transition: '0.2s' }}
            />
          </div>
        </div>
      </div>

      {open && match.pred && (
        <div style={{ marginTop: '16px', borderTop: '1px solid #333333', paddingTop: '16px' }}>
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '13px', fontWeight: '600', color: '#F5F5F5', marginBottom: '10px' }}>
              Résultat final
            </div>
            <ProbBar label="Victoire domicile" value={match.pred.prob_home_win} color="#2563EB" />
            <ProbBar label="Match nul" value={match.pred.prob_draw} color="#D97706" />
            <ProbBar label="Victoire extérieur" value={match.pred.prob_away_win} color="#DC2626" />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '13px', fontWeight: '600', color: '#F5F5F5', marginBottom: '10px' }}>
              Buts
            </div>
            <ProbBar label="Plus de 2.5 buts" value={match.pred.prob_over25} color={match.pred.prob_over25 > 0.60 ? '#16A34A' : '#A0A0A0'} />
            <ProbBar label="Les deux équipes marquent" value={match.pred.prob_btts} color={match.pred.prob_btts > 0.55 ? '#16A34A' : '#A0A0A0'} />
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '8px',
            backgroundColor: '#1A1A1A',
            borderRadius: '8px',
            padding: '12px',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Score probable</div>
              <div style={{ fontSize: '16px', fontWeight: '700', color: '#F5F5F5' }}>
                {match.pred.most_likely_score}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Lambda</div>
              <div style={{ fontSize: '16px', fontWeight: '700', color: '#2563EB' }}>
                {match.pred.dc_lambda.toFixed(2)}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Mu</div>
              <div style={{ fontSize: '16px', fontWeight: '700', color: '#DC2626' }}>
                {match.pred.dc_mu.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Analyse() {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ paddingTop: '8px', marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>
          Analyse
        </h1>
        <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>
          Détail des prédictions
        </p>
      </div>

      <div style={{ marginBottom: '16px' }}>
        {mockMatchs.map(match => (
          <MatchAnalyse key={match.id} match={match} />
        ))}
      </div>
    </div>
  )
}
