import React, { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw, Database, Brain, Activity, Clock,
  CheckCircle, XCircle, AlertCircle, Play, Loader,
  TrendingUp, BarChart2, Zap, Shield
} from 'lucide-react'
import api from '../services/api.js'

const STATUS_COLOR = {
  completed: '#22C55E',
  running:   '#3B82F6',
  failed:    '#EF4444',
  pending:   '#F59E0B',
}

const STATUS_ICON = {
  completed: <CheckCircle size={14} />,
  running:   <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />,
  failed:    <XCircle size={14} />,
  pending:   <AlertCircle size={14} />,
}

function Card({ title, icon, children, accent }) {
  return (
    <div style={{
      backgroundColor: '#1A1A1A',
      border: `1px solid ${accent || '#2A2A2A'}`,
      borderRadius: '12px',
      padding: '16px',
      marginBottom: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ color: accent || '#666' }}>{icon}</span>
        <span style={{ fontWeight: '600', fontSize: '13px', color: '#E5E5E5' }}>{title}</span>
      </div>
      {children}
    </div>
  )
}

function Stat({ label, value, sub, color }) {
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontSize: '12px', color: '#888' }}>{label}</span>
        <span style={{ fontSize: '14px', fontWeight: '600', color: color || '#F5F5F5' }}>
          {value ?? '—'}
        </span>
      </div>
      {sub && <div style={{ fontSize: '11px', color: '#555', textAlign: 'right' }}>{sub}</div>}
    </div>
  )
}

function ActionButton({ label, icon, onClick, loading, color }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '8px 14px',
        borderRadius: '8px',
        border: `1px solid ${color || '#3B82F6'}`,
        backgroundColor: loading ? '#1A1A1A' : 'transparent',
        color: loading ? '#555' : (color || '#3B82F6'),
        fontSize: '12px',
        fontWeight: '500',
        cursor: loading ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s',
      }}
    >
      {loading ? <Loader size={13} /> : icon}
      {label}
    </button>
  )
}

function JobRow({ job }) {
  const color = STATUS_COLOR[job.status] || '#666'
  const icon = STATUS_ICON[job.status] || null
  const duration = job.execution_time_ms
    ? job.execution_time_ms < 1000
      ? `${job.execution_time_ms}ms`
      : `${(job.execution_time_ms / 1000).toFixed(1)}s`
    : job.status === 'running' ? '…' : '—'

  const startedAt = job.started_at
    ? new Date(job.started_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  const jobLabel = {
    sync_leagues: 'Sync ligues',
    market_refresh: 'Refresh marchés',
    resolution: 'Résolution pronos',
    model_retrain: 'Réentraînement ML',
    historical_feature_backfill: 'Backfill features',
    daily_backup: 'Sauvegarde DB',
  }[job.job_name] || job.job_name

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 0',
      borderBottom: '1px solid #222',
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color }}>{icon}</span>
          <span style={{ fontSize: '12px', color: '#DDD' }}>{jobLabel}</span>
        </div>
        {job.error_message && (
          <div style={{ fontSize: '10px', color: '#EF4444', marginTop: '2px', paddingLeft: '20px' }}>
            {job.error_message.slice(0, 60)}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', minWidth: '80px' }}>
        <div style={{ fontSize: '11px', color: '#666' }}>{startedAt}</div>
        <div style={{ fontSize: '11px', color }}>
          {duration}
        </div>
      </div>
    </div>
  )
}

export default function Admin() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [error, setError] = useState(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get('/system/status')
      if (res.success) {
        setData(res.data)
        setLastRefresh(new Date())
        setError(null)
      }
    } catch (e) {
      setError('Impossible de contacter le serveur')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const runAction = async (endpoint, label) => {
    setActionLoading(label)
    try {
      const res = await api.post(`/system/${endpoint}`)
      if (!res.success) {
        setError(res.error?.message || `Erreur ${endpoint}`)
      }
      await fetchStatus()
    } catch (e) {
      setError(`Erreur: ${e.message}`)
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) return (
    <div style={{ padding: '24px', textAlign: 'center', color: '#666', marginTop: '80px' }}>
      <Loader size={24} style={{ animation: 'spin 1s linear infinite' }} />
      <div style={{ marginTop: '8px', fontSize: '13px' }}>Chargement du statut système…</div>
    </div>
  )

  const db = data?.db || {}
  const modele = data?.modele || {}
  const pronos = data?.pronostics || {}
  const jobs = data?.jobs || []
  const features = data?.features_historiques || {}

  const featuresManquantes = features.features_historiques_manquantes || 0
  const featuresCompletes = features.features_historiques_completes || 0
  const featuresTotales = featuresManquantes + featuresCompletes
  const featuresPct = featuresTotales > 0
    ? Math.round(featuresCompletes / featuresTotales * 100)
    : 0

  return (
    <div style={{ padding: '16px', paddingBottom: '90px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingTop: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={18} color="#F59E0B" />
          <span style={{ fontWeight: '700', fontSize: '16px' }}>Administration</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {lastRefresh && (
            <span style={{ fontSize: '10px', color: '#555' }}>
              {lastRefresh.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            onClick={fetchStatus}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#666', padding: '4px' }}
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          backgroundColor: '#1F0000', border: '1px solid #7F1D1D',
          borderRadius: '8px', padding: '10px 12px', marginBottom: '12px',
          fontSize: '12px', color: '#FCA5A5',
        }}>
          {error}
        </div>
      )}

      {/* Actions */}
      <Card title="Actions manuelles" icon={<Zap size={15} />} accent="#F59E0B">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <ActionButton
            label="Sync légère"
            icon={<RefreshCw size={13} />}
            loading={actionLoading === 'manual-sync'}
            onClick={() => runAction('manual-sync', 'manual-sync')}
            color="#3B82F6"
          />
          <ActionButton
            label="Backfill features"
            icon={<Database size={13} />}
            loading={actionLoading === 'manual-feature-backfill'}
            onClick={() => runAction('manual-feature-backfill', 'manual-feature-backfill')}
            color="#8B5CF6"
          />
          <ActionButton
            label="Résoudre pronos"
            icon={<CheckCircle size={13} />}
            loading={actionLoading === 'auto-resolve-pronostics'}
            onClick={() => runAction('auto-resolve-pronostics', 'auto-resolve-pronostics')}
            color="#22C55E"
          />
          <ActionButton
            label="Réentraîner ML"
            icon={<Brain size={13} />}
            loading={actionLoading === 'manual-retrain'}
            onClick={() => runAction('manual-retrain', 'manual-retrain')}
            color="#EC4899"
          />
          <ActionButton
            label="Pipeline complet"
            icon={<Play size={13} />}
            loading={actionLoading === 'pipeline-complet'}
            onClick={() => runAction('pipeline-complet', 'pipeline-complet')}
            color="#F59E0B"
          />
        </div>
      </Card>

      {/* DB Stats */}
      <Card title="Base de données" icon={<Database size={15} />} accent="#3B82F6">
        <Stat label="Matchs total" value={db.total_matchs?.toLocaleString('fr-FR')} />
        <Stat label="Matchs à venir" value={db.matchs_a_venir?.toLocaleString('fr-FR')} />
        <Stat label="Matchs complets" value={db.matchs_complets?.toLocaleString('fr-FR')} />
        <Stat label="Ligues actives" value={`${db.ligues_actives} / ${db.total_ligues}`} />
        <Stat label="Cotes en base" value={db.total_odds?.toLocaleString('fr-FR')} />
        <Stat
          label="Données HT"
          value={`${db.ht_coverage_pct}%`}
          sub={`${db.ht_avec_donnees?.toLocaleString('fr-FR')} matchs`}
          color={db.ht_coverage_pct > 50 ? '#22C55E' : db.ht_coverage_pct > 10 ? '#F59E0B' : '#EF4444'}
        />
        <Stat
          label="Features ML"
          value={`${featuresPct}%`}
          sub={`${featuresCompletes?.toLocaleString('fr-FR')} / ${featuresTotales?.toLocaleString('fr-FR')} • ${featuresManquantes?.toLocaleString('fr-FR')} manquantes`}
          color={featuresPct > 80 ? '#22C55E' : '#F59E0B'}
        />
      </Card>

      {/* Modèle ML */}
      <Card title="Modèle ML" icon={<Brain size={15} />} accent="#EC4899">
        <Stat label="Version" value={modele.version || '—'} />
        <Stat label="Entraîné le" value={modele.trained_at ? new Date(modele.trained_at).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'} />
        <Stat label="Matchs entraînés" value={modele.total_matches_trained?.toLocaleString('fr-FR')} />
        <Stat
          label="AUC-ROC (over25)"
          value={modele.auc_roc_over25 ? modele.auc_roc_over25.toFixed(4) : '—'}
          color={modele.auc_roc_over25 > 0.6 ? '#22C55E' : modele.auc_roc_over25 > 0.55 ? '#F59E0B' : '#EF4444'}
        />
        <Stat
          label="Brier Score (over25)"
          value={modele.brier_score_over25 ? modele.brier_score_over25.toFixed(4) : '—'}
          sub="plus bas = meilleur"
          color={modele.brier_score_over25 < 0.22 ? '#22C55E' : '#F59E0B'}
        />
      </Card>

      {/* Pronostics */}
      <Card title="Pronostics" icon={<TrendingUp size={15} />} accent="#22C55E">
        {Object.entries({
          pending:    ['En attente', '#F59E0B'],
          placed:     ['Placés', '#3B82F6'],
          won:        ['Gagnés', '#22C55E'],
          lost:       ['Perdus', '#EF4444'],
          void:       ['Annulés', '#666'],
          ignored:    ['Ignorés', '#555'],
          superseded: ['Remplacés', '#444'],
        }).map(([key, [label, color]]) => (
          pronos[key] !== undefined && (
            <Stat key={key} label={label} value={pronos[key]?.toLocaleString('fr-FR')} color={color} />
          )
        ))}
      </Card>

      {/* Jobs Scheduler */}
      <Card title="Tâches automatiques (30 dernières)" icon={<Activity size={15} />} accent="#8B5CF6">
        {jobs.length === 0 ? (
          <div style={{ fontSize: '12px', color: '#555', textAlign: 'center', padding: '12px 0' }}>
            Aucune tâche enregistrée
          </div>
        ) : (
          jobs.map((job, i) => <JobRow key={i} job={job} />)
        )}
      </Card>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
      `}</style>
    </div>
  )
}
