import React, { useState } from 'react'
import api from '../services/api.js'

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('vagharlegrand@gmail.com')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/auth/login', {
        email,
        password,
        device_fingerprint: 'pwa-device-' + navigator.userAgent.slice(0, 20),
        device_name: navigator.platform || 'Mon appareil',
        platform: /iPhone|iPad/.test(navigator.userAgent) ? 'iOS' : 'web',
      })
      const token = res.data.access_token
      localStorage.setItem('token', token)
      onLogin(token)
    } catch (e) {
      setError('Email ou mot de passe incorrect')
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
            Système de pronostics intelligent
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ fontSize: '12px', color: '#666666', display: 'block', marginBottom: '6px' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              placeholder="Cerveau2026!"
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

          {error && (
            <p style={{ fontSize: '13px', color: '#DC2626', textAlign: 'center' }}>
              {error}
            </p>
          )}

          <button
            onClick={handleLogin}
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
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </div>
      </div>
    </div>
  )
}
