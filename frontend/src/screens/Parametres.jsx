import React, { useEffect, useState } from 'react'
import { User, Shield, Bell, TrendingUp, LogOut, Sliders } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'
import api from '../services/api.js'

export default function Parametres({ onLogout }) {
  const [kelly, setKelly] = useState('1/8')
  const [notifications, setNotifications] = useState(true)
  const [profile, setProfile] = useState(null)
  const [systemStatus, setSystemStatus] = useState(null)
  const [modelHealth, setModelHealth] = useState(null)
  const [isSyncingLeagues, setIsSyncingLeagues] = useState(false)
  const [leagueSyncFeedback, setLeagueSyncFeedback] = useState('')
  const [isBackfilling, setIsBackfilling] = useState(false)
  const [backfillFeedback, setBackfillFeedback] = useState('')
  const [isRetraining, setIsRetraining] = useState(false)
  const [retrainFeedback, setRetrainFeedback] = useState('')

  const fractions = [
    { id: '1/8', label: '1/8 — Très conservateur', value: 0.125 },
    { id: '1/6', label: '1/6 — Conservateur', value: 0.167 },
    { id: '1/4', label: '1/4 — Modéré', value: 0.25 },
  ]

  const chargerDonnees = async () => {
    try {
      const [me, status, perf] = await Promise.all([
        api.get('/auth/me'),
        api.get('/system/status'),
        api.get('/performance/summary'),
      ])

      setProfile(me.data)
      setSystemStatus(status.data)
      setModelHealth(perf.data?.model_health || null)

      const profileKelly = me.data?.kelly_fraction
      const fraction = fractions.find((item) => item.value === profileKelly)
      if (fraction) {
        setKelly(fraction.id)
      }
    } catch (e) {
      // L'écran garde ses valeurs de repli si l'API n'est pas disponible.
    }
  }

  useEffect(() => {
    chargerDonnees()
  }, [])

  const lancerSyncLigues = async () => {
    setIsSyncingLeagues(true)
    setLeagueSyncFeedback('')

    try {
      const response = await api.post(
        '/system/manual-league-sync',
        {},
        { timeout: 300000 }
      )

      const sync = response.data?.sync?.sync_ligues || {}
      const saisonsCollectees = response.data?.sync?.saisons_collectees ?? '—'
      const pipelineTriggered = Boolean(response.data?.pipeline_triggered)
      const backfill = response.data?.backfill || {}
      const refresh = response.data?.refresh || {}

      if (pipelineTriggered) {
        setLeagueSyncFeedback(
          `Catalogue synchronisé puis pipeline lancé automatiquement: ${sync.total_actives_db ?? '—'} ligues actives, ${saisonsCollectees} saisons collectées, ${backfill.batches ?? '—'} lot(s) de backfill, ${refresh.pronostics?.inserted ?? 0} pronostic(s) régénéré(s).`
        )
      } else {
        setLeagueSyncFeedback(
          `Catalogue synchronisé: aucun changement détecté, donc pas de backfill ni de réentraînement relancés.`
        )
      }
      await chargerDonnees()
    } catch (e) {
      const message =
        e?.error?.message ||
        e?.detail ||
        e?.message ||
        "Impossible de synchroniser les ligues disponibles."
      setLeagueSyncFeedback(message)
    } finally {
      setIsSyncingLeagues(false)
    }
  }

  const lancerBackfill = async () => {
    setIsBackfilling(true)
    setBackfillFeedback('')

    try {
      const response = await api.post(
        '/system/manual-feature-backfill',
        {},
        { timeout: 120000 }
      )

      const processed = response.data?.processed || 0
      const remaining = response.data?.after?.features_historiques_manquantes

      setBackfillFeedback(`Lot traité: ${processed} matchs. Reste: ${remaining ?? '—'}.`)
      await chargerDonnees()
    } catch (e) {
      const message =
        e?.error?.message ||
        e?.detail ||
        e?.message ||
        "Impossible de lancer le backfill historique."
      setBackfillFeedback(message)
    } finally {
      setIsBackfilling(false)
    }
  }

  const lancerEntrainement = async () => {
    setIsRetraining(true)
    setRetrainFeedback('')

    try {
      const response = await api.post(
        '/system/manual-retrain',
        {},
        { timeout: 120000 }
      )

      if (response.data?.trained) {
        setRetrainFeedback(`Entraînement terminé. Version ${response.data.model_health?.model_version || 'mise à jour'}.`)
      } else {
        setRetrainFeedback("Entraînement lancé, mais aucune nouvelle version n'a été produite.")
      }

      await chargerDonnees()
    } catch (e) {
      const message =
        e?.error?.message ||
        e?.detail ||
        e?.message ||
        "Impossible de lancer l'entraînement."
      setRetrainFeedback(message)
    } finally {
      setIsRetraining(false)
    }
  }

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout')
    } catch (e) {
      // Même si le backend ne répond pas, on ferme la session locale.
    } finally {
      localStorage.removeItem('token')
      if (onLogout) {
        onLogout()
      }
    }
  }

  const sections = [
    {
      title: 'Compte',
      icon: User,
      items: [
        { label: 'Email', value: profile?.email || '—' },
        { label: 'Bankroll initiale', value: profile ? `${profile.initial_bankroll.toFixed(2)}€` : '—' },
        { label: 'Bankroll actuelle', value: profile ? `${profile.current_bankroll.toFixed(2)}€` : '—' },
      ]
    },
    {
      title: 'Système',
      icon: Sliders,
      items: [
        {
          label: 'Mode actuel',
          value: systemStatus?.system_mode === 'active' ? 'Actif' : (systemStatus?.system_mode || '—'),
          badge: systemStatus?.system_mode === 'active' ? 'success' : 'muted'
        },
        { label: 'API', value: systemStatus?.api_status || '—' },
        { label: 'Catalogue ligues', value: systemStatus ? `${systemStatus.ligues_actives ?? '—'} actives / ${systemStatus.total_ligues ?? '—'} total` : '—' },
        { label: 'Matchs à venir', value: systemStatus?.matchs_a_venir ?? '—' },
      ]
    },
    {
      title: 'Sécurité',
      icon: Shield,
      items: [
        { label: 'Appareils autorisés', value: '1 appareil' },
        { label: 'Dernière connexion', value: "Aujourd'hui" },
      ]
    },
  ]

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ paddingTop: '8px', marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#F5F5F5' }}>
          Paramètres
        </h1>
        <p style={{ fontSize: '13px', color: '#666666', marginTop: '2px' }}>
          Configuration du système
        </p>
      </div>

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5', marginBottom: '14px' }}>
          Fraction Kelly
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {fractions.map(f => (
            <button
              key={f.id}
              onClick={() => setKelly(f.id)}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px',
                borderRadius: '10px',
                border: `1px solid ${kelly === f.id ? '#2563EB' : '#333333'}`,
                backgroundColor: kelly === f.id ? '#2563EB11' : 'transparent',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: '13px', color: kelly === f.id ? '#2563EB' : '#A0A0A0', fontWeight: kelly === f.id ? '600' : '400' }}>
                {f.label}
              </span>
              {kelly === f.id && (
                <div style={{ width: '8px', height: '8px', borderRadius: '9999px', backgroundColor: '#2563EB' }} />
              )}
            </button>
          ))}
        </div>
      </Card>

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Bell size={18} color="#A0A0A0" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5' }}>
                Notifications
              </div>
              <div style={{ fontSize: '12px', color: '#666666', marginTop: '2px' }}>
                Pronostics et résultats
              </div>
            </div>
          </div>
          <button
            onClick={() => setNotifications(!notifications)}
            style={{
              width: '44px',
              height: '24px',
              borderRadius: '9999px',
              border: 'none',
              backgroundColor: notifications ? '#2563EB' : '#333333',
              cursor: 'pointer',
              position: 'relative',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{
              width: '18px',
              height: '18px',
              borderRadius: '9999px',
              backgroundColor: '#FFFFFF',
              position: 'absolute',
              top: '3px',
              left: notifications ? '23px' : '3px',
              transition: 'left 0.2s',
            }} />
          </button>
        </div>
      </Card>

      {sections.map(section => (
        <Card key={section.title} style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <section.icon size={16} color="#666666" />
            <span style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5' }}>
              {section.title}
            </span>
          </div>
          {section.items.map((item, i) => (
            <div
              key={item.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingBottom: i < section.items.length - 1 ? '12px' : 0,
                marginBottom: i < section.items.length - 1 ? '12px' : 0,
                borderBottom: i < section.items.length - 1 ? '1px solid #2E2E2E' : 'none',
              }}
            >
              <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
              {item.badge ? (
                <Badge variant={item.badge}>{item.value}</Badge>
              ) : (
                <span style={{ fontSize: '13px', fontWeight: '500', color: '#F5F5F5' }}>
                  {item.value}
                </span>
              )}
            </div>
          ))}
        </Card>
      ))}

      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <TrendingUp size={16} color="#666666" />
          <span style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5' }}>
            Entraînement
          </span>
        </div>

        {[
          { label: 'Version du modèle', value: modelHealth?.model_version || '—' },
          { label: 'Dernier entraînement', value: modelHealth?.last_retrain || '—' },
          { label: 'Brier Score', value: modelHealth?.brier_score ? modelHealth.brier_score.toFixed(4) : '—' },
          { label: 'AUC-ROC', value: modelHealth?.auc_roc ? modelHealth.auc_roc.toFixed(4) : '—' },
          { label: 'Fréquence du retrain', value: 'Toutes les 24h' },
          { label: 'Premier retrain après redémarrage', value: '10 min' },
        ].map((item, i, arr) => (
          <div
            key={item.label}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingBottom: i < arr.length - 1 ? '12px' : 0,
              marginBottom: i < arr.length - 1 ? '12px' : 0,
              borderBottom: i < arr.length - 1 ? '1px solid #2E2E2E' : 'none',
            }}
          >
            <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
            <span style={{ fontSize: '13px', fontWeight: '500', color: '#F5F5F5' }}>
              {item.value}
            </span>
          </div>
        ))}

        {profile?.is_admin ? (
          <>
            <button
              onClick={lancerEntrainement}
              disabled={isRetraining || isBackfilling}
              style={{
                width: '100%',
                marginTop: '16px',
                padding: '12px',
                borderRadius: '10px',
                border: '1px solid #2563EB33',
                backgroundColor: isRetraining ? '#1D4ED822' : '#2563EB22',
                color: '#60A5FA',
                fontSize: '13px',
                fontWeight: '600',
                cursor: isRetraining ? 'wait' : 'pointer',
                opacity: isRetraining ? 0.7 : 1,
              }}
            >
              {isRetraining ? "Entraînement en cours..." : "Lancer l'entraînement maintenant"}
            </button>

            {retrainFeedback && (
              <div style={{ marginTop: '12px', fontSize: '12px', color: '#A0A0A0' }}>
                {retrainFeedback}
              </div>
            )}
          </>
        ) : (
          <div style={{ marginTop: '16px', fontSize: '12px', color: '#666666' }}>
            Action réservée à l'administrateur.
          </div>
        )}
      </Card>

      {profile?.is_admin && (
        <Card style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Sliders size={16} color="#666666" />
            <span style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5' }}>
              Catalogue ligues
            </span>
          </div>

          {[
            { label: 'Ligues actives', value: systemStatus?.ligues_actives ?? '—' },
            { label: 'Ligues totales en base', value: systemStatus?.total_ligues ?? '—' },
            { label: 'Pipeline après changement', value: 'Automatique: backfill, entraînement, pronostics' },
          ].map((item, i, arr) => (
            <div
              key={item.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '12px',
                paddingBottom: i < arr.length - 1 ? '12px' : 0,
                marginBottom: i < arr.length - 1 ? '12px' : 0,
                borderBottom: i < arr.length - 1 ? '1px solid #2E2E2E' : 'none',
              }}
            >
              <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
              <span style={{ fontSize: '13px', fontWeight: '500', color: '#F5F5F5', textAlign: 'right' }}>
                {item.value}
              </span>
            </div>
          ))}

          <button
            onClick={lancerSyncLigues}
            disabled={isSyncingLeagues || isBackfilling || isRetraining}
            style={{
              width: '100%',
              marginTop: '16px',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid #EAB30833',
              backgroundColor: isSyncingLeagues ? '#A1620722' : '#EAB30822',
              color: '#FACC15',
              fontSize: '13px',
              fontWeight: '600',
              cursor: isSyncingLeagues ? 'wait' : 'pointer',
              opacity: isSyncingLeagues ? 0.7 : 1,
            }}
          >
            {isSyncingLeagues ? 'Synchronisation des ligues...' : 'Prendre les ligues disponibles'}
          </button>

          {leagueSyncFeedback && (
            <div style={{ marginTop: '12px', fontSize: '12px', color: '#A0A0A0' }}>
              {leagueSyncFeedback}
            </div>
          )}
        </Card>
      )}

      {profile?.is_admin && (
        <Card style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Sliders size={16} color="#666666" />
            <span style={{ fontSize: '14px', fontWeight: '600', color: '#F5F5F5' }}>
              Backfill historique
            </span>
          </div>

          {[
            { label: 'Matchs complets', value: systemStatus?.matches_complete ?? '—' },
            { label: 'Features calculées', value: systemStatus?.features_historiques_calculees ?? '—' },
            { label: 'Backlog restant', value: systemStatus?.features_historiques_manquantes ?? '—' },
            {
              label: 'Couverture',
              value: systemStatus?.historical_backfill_coverage_pct !== undefined
                ? `${systemStatus.historical_backfill_coverage_pct}%`
                : '—'
            },
          ].map((item, i, arr) => (
            <div
              key={item.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingBottom: i < arr.length - 1 ? '12px' : 0,
                marginBottom: i < arr.length - 1 ? '12px' : 0,
                borderBottom: i < arr.length - 1 ? '1px solid #2E2E2E' : 'none',
              }}
            >
              <span style={{ fontSize: '13px', color: '#A0A0A0' }}>{item.label}</span>
              <span style={{ fontSize: '13px', fontWeight: '500', color: '#F5F5F5' }}>
                {item.value}
              </span>
            </div>
          ))}

          <button
            onClick={lancerBackfill}
            disabled={isBackfilling || isRetraining}
            style={{
              width: '100%',
              marginTop: '16px',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid #16A34A33',
              backgroundColor: isBackfilling ? '#16653422' : '#16A34A22',
              color: '#4ADE80',
              fontSize: '13px',
              fontWeight: '600',
              cursor: isBackfilling ? 'wait' : 'pointer',
              opacity: isBackfilling ? 0.7 : 1,
            }}
          >
            {isBackfilling ? 'Backfill en cours...' : 'Lancer un lot de backfill'}
          </button>

          {backfillFeedback && (
            <div style={{ marginTop: '12px', fontSize: '12px', color: '#A0A0A0' }}>
              {backfillFeedback}
            </div>
          )}
        </Card>
      )}

      <button
        onClick={handleLogout}
        style={{
          width: '100%',
          padding: '14px',
          borderRadius: '12px',
          border: '1px solid #DC262633',
          backgroundColor: '#DC262611',
          color: '#DC2626',
          fontSize: '14px',
          fontWeight: '600',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
        }}
      >
        <LogOut size={16} />
        Se déconnecter
      </button>
    </div>
  )
}
