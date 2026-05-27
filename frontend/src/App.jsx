import { useState } from 'react'
import Auth from './components/Auth.jsx'
import Chat from './components/Chat.jsx'
import Dashboard from './components/Dashboard.jsx'

function getStoredAuth() {
  const token = localStorage.getItem('token')
  const email = localStorage.getItem('email')
  if (!token || !email) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('token')
      localStorage.removeItem('email')
      return null
    }
  } catch {
    return null
  }
  return { token, email }
}

export default function App() {
  const [auth, setAuth] = useState(getStoredAuth)
  const [tab, setTab] = useState('chat')

  function handleLogin(email) {
    setAuth({ email, token: localStorage.getItem('token') })
  }

  function handleLogout() {
    localStorage.removeItem('token')
    localStorage.removeItem('email')
    setAuth(null)
  }

  if (!auth) return <Auth onLogin={handleLogin} />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
      {/* Header */}
      <header style={{
        background: 'rgba(9,9,18,0.9)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)',
        padding: '0 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '58px',
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            width: '30px',
            height: '30px',
            background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.9rem',
            boxShadow: '0 4px 12px rgba(124,58,237,0.4)',
            flexShrink: 0,
          }}>
            🎫
          </div>
          <span style={{ fontWeight: 700, fontSize: '0.95rem', letterSpacing: '-0.02em', color: 'var(--text)' }}>
            Live Events
          </span>
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            background: 'linear-gradient(90deg, #7c3aed, #3b82f6)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            marginLeft: '-0.1rem',
          }}>
            Ticket Agent
          </span>
        </div>

        {/* Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '99px',
            padding: '0.3rem 0.75rem 0.3rem 0.4rem',
          }}>
            <div style={{
              width: '22px',
              height: '22px',
              background: 'linear-gradient(135deg, #7c3aed, #ec4899)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.6rem',
              fontWeight: 700,
              color: '#fff',
              flexShrink: 0,
            }}>
              {auth.email[0].toUpperCase()}
            </div>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-2)', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {auth.email}
            </span>
          </div>
          <button
            onClick={handleLogout}
            style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              color: 'var(--text-2)',
              padding: '0.35rem 0.8rem',
              fontSize: '0.78rem',
              borderRadius: '99px',
            }}
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        flexShrink: 0,
        padding: '0 1.5rem',
        gap: '0.25rem',
      }}>
        {[
          { id: 'chat',      label: 'Chat',             icon: '💬' },
          { id: 'dashboard', label: 'My Subscriptions', icon: '🔔' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none',
              borderRadius: 0,
              padding: '0.85rem 1rem',
              fontWeight: tab === t.id ? 600 : 400,
              color: tab === t.id ? 'var(--text)' : 'var(--text-3)',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'color 0.15s',
            }}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'chat' ? <Chat /> : <Dashboard />}
      </main>
    </div>
  )
}
