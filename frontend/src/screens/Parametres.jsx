import React, { useState } from 'react'
import { User, Shield, Bell, TrendingUp, ChevronRight, LogOut, Sliders } from 'lucide-react'
import Card from '../components/shared/Card.jsx'
import Badge from '../components/shared/Badge.jsx'

export default function Parametres() {
  const [kelly, setKelly] = useState('1/8')
  const [notifications, setNotifications] = useState(true)

  const fractions = [
    { id: '1/8', label: '1/8 — Très conservateur', value: 0.125 },
    { id: '1/6', label: '1/6 — Conservateur', value: 0.167 },
    { id: '1/4', label: '1/4 — Modéré', value: 0.25 },
  ]

  const sections = [
    {
      title: 'Compte',
      icon: User,
      items: [
        { label: 'Email', value: 'vagharlegrand@gmail.com' },
        { label: 'Bankroll initiale', value: '150.00€' },
        { label: 'Bankroll actuelle', value: '150.00€' },
      ]
    },
    {
      title: 'Système',
      icon: Sliders,
      items: [
        { label: 'Mode actuel', value: 'Actif', badge: 'success' },
        { label: 'Marchés actifs', value: 'Over 2.5, BTTS' },
        { label: 'Ligues suivies', value: '6 ligues' },
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

      <button
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
