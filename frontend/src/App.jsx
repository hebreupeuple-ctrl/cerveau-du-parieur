import React, { useEffect, useState } from 'react'
import { Provider } from 'react-redux'
import { store } from './store/index.js'
import BottomNav from './components/navigation/BottomNav.jsx'
import Aujourd_hui from './screens/Aujourd_hui.jsx'
import Performance from './screens/Performance.jsx'
import Historique from './screens/Historique.jsx'
import Analyse from './screens/Analyse.jsx'
import Parametres from './screens/Parametres.jsx'

const screens = {
  today: Aujourd_hui,
  performance: Performance,
  historique: Historique,
  analyse: Analyse,
  parametres: Parametres,
}

function AppContent() {
  const [activeScreen, setActiveScreen] = useState('today')
  const Screen = screens[activeScreen]

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0F0F0F',
      color: '#F5F5F5',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
      maxWidth: '430px',
      margin: '0 auto',
      position: 'relative',
    }}>
      <div style={{ paddingBottom: '80px' }}>
        <Screen />
      </div>
      <BottomNav active={activeScreen} onChange={setActiveScreen} />
    </div>
  )
}

export default function App() {
  return (
    <Provider store={store}>
      <AppContent />
    </Provider>
  )
}
