import React, { useState } from 'react'
import api from '../services/api.js'

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const devicePayload = {
    device_fingerprint: 'pwa-device-' + navigator.userAgent.slice(0, 20),
    device_name: navigator.platform || 'Mon appareil',
    platform: /iPhone|iPad/.test(navigator.userAgent) ? 'iOS' : 'web',
  }

  const resetErrors = () => {
    setError(null)
  }

  const basculerMode = (nextMode) => {
    setMode(nextMode)
    setPassword('')
    setConfirmPassword('')
    setError(null)
  }

  const handleSubmit = async () => {
    if (!email.trim() || !password.trim()) {
      setError('Renseigne ton email et ton mot de passe')
      return
    }

    if (mode === 'register') {
      if (password.length < 8) {
        setError('Le mot de passe doit contenir au moins 8 caractères')
        return
      }

      if (password !== confirmPassword) {
        setError('Les mots de passe ne correspondent pas')
        return
      }
    }

    setLoading(true)
    setError(null)

    try {
      if (mode === 'register') {
        await api.post('/auth/register', {
          email: email.trim(),
          password,
        })
      }

      const res = await api.post('/auth/login', {
        email: email.trim(),
        password,
        ...devicePayload,
      })
      const token = res.data.access_token
      localStorage.setItem('token', token)
      onLogin(token)
    } catch (e) {
      const message = e?.detail?.message || e?.error?.message

      if (mode === 'register') {
        setError(message || 'Impossible de créer le compte')
      } else {
        setError(message || 'Email ou mot de passe incorrect')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0F0F0F',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: '360px' }}>
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            width: '64px', height: '64px',
            backgroundColor: '#2563EB',
            borderRadius: '18px',
            display: 'flex', alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            fontSize: '28px',
          }}>
            🧠
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#F5F5F5', marginBottom: '6px' }}>
            Cerveau du Parieur
          </h1>
          <p style={{ fontSize: '13px', color: '#666666' }}>
            {mode === 'login'
              ? 'Connecte-toi pour voir tes pronostics'
              : 'Crée ton compte pour démarrer'}
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
            marginBottom: '4px',
          }}>
            <button
              onClick={() => basculerMode('login')}
              disabled={loading}
              style={{
                padding: '11px',
                borderRadius: '10px',
                border: '1px solid ' + (mode === 'login' ? '#2563EB' : '#333333'),
                backgroundColor: mode === 'login' ? '#111C34' : '#1A1A1A',
                color: mode === 'login' ? '#F5F5F5' : '#8A8A8A',
                fontSize: '14px',
                fontWeight: '600',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              Se connecter
            </button>
            <button
              onClick={() => basculerMode('register')}
              disabled={loading}
              style={{
                padding: '11px',
                borderRadius: '10px',
                border: '1px solid ' + (mode === 'register' ? '#2563EB' : '#333333'),
                backgroundColor: mode === 'register' ? '#111C34' : '#1A1A1A',
                color: mode === 'register' ? '#F5F5F5' : '#8A8A8A',
                fontSize: '14px',
                fontWeight: '600',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              Créer un compte
            </button>
          </div>

          <div>
            <label style={{ fontSize: '12px', color: '#666666', display: 'block', marginBottom: '6px' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                resetErrors()
              }}
              placeholder="votre@email.com"
              style={{
                width: '100%',
                backgroundColor: '#1A1A1A',
                border: '1px solid #333333',
                borderRadius: '10px',
                padding: '13px 14px',
                color: '#F5F5F5',
                fontSize: '15px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: '12px', color: '#666666', display: 'block', marginBottom: '6px' }}>
              Mot de passe
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                resetErrors()
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder={mode === 'register' ? 'Au moins 8 caractères' : 'Votre mot de passe'}
              style={{
                width: '100%',
                backgroundColor: '#1A1A1A',
                border: '1px solid #333333',
                borderRadius: '10px',
                padding: '13px 14px',
                color: '#F5F5F5',
                fontSize: '15px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label style={{ fontSize: '12px', color: '#666666', display: 'block', marginBottom: '6px' }}>
                Confirmer le mot de passe
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  resetErrors()
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                placeholder="Répète le mot de passe"
                style={{
                  width: '100%',
                  backgroundColor: '#1A1A1A',
                  border: '1px solid #333333',
                  borderRadius: '10px',
                  padding: '13px 14px',
                  color: '#F5F5F5',
                  fontSize: '15px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          )}

          {mode === 'register' && (
            <p style={{ fontSize: '12px', color: '#666666', lineHeight: '1.5', margin: 0 }}>
              Le compte est créé puis connecté automatiquement avec la bankroll par défaut.
            </p>
          )}

          {error && (
            <p style={{ fontSize: '13px', color: '#DC2626', textAlign: 'center' }}>
              {error}
            </p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '12px',
              border: 'none',
              backgroundColor: loading ? '#1D4ED8' : '#2563EB',
              color: '#FFFFFF',
              fontSize: '15px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: '8px',
            }}
          >
            {loading
              ? (mode === 'login' ? 'Connexion...' : 'Création...')
              : (mode === 'login' ? 'Se connecter' : 'Créer mon compte')}
          </button>
        </div>
      </div>
    </div>
  )
}
