import { useState } from 'react'
import { apiPost } from '../api'

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
      const data = await apiPost(endpoint, { email, password })
      localStorage.setItem('token', data.token)
      localStorage.setItem('email', data.email)
      onLogin(data.email)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'radial-gradient(ellipse at 60% 0%, rgba(124,58,237,0.18) 0%, transparent 60%), radial-gradient(ellipse at 0% 100%, rgba(59,130,246,0.12) 0%, transparent 50%), var(--bg)',
      padding: '1.5rem',
    }}>
      {/* Card */}
      <div className="fade-up" style={{
        width: '100%',
        maxWidth: '400px',
        background: 'rgba(15,15,26,0.85)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '2.5rem',
        boxShadow: '0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04) inset',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '52px',
            height: '52px',
            background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
            borderRadius: '14px',
            fontSize: '1.5rem',
            marginBottom: '1rem',
            boxShadow: '0 8px 24px rgba(124,58,237,0.4)',
          }}>
            🎫
          </div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.02em' }}>
            Live Events Ticket Agent
          </h1>
          <p style={{ fontSize: '0.83rem', color: 'var(--text-2)', marginTop: '0.35rem' }}>
            {mode === 'login' ? 'Welcome back — sign in to continue' : 'Create your account to get started'}
          </p>
        </div>

        {/* Mode toggle pills */}
        <div style={{
          display: 'flex',
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '10px',
          padding: '3px',
          marginBottom: '1.5rem',
          gap: '3px',
        }}>
          {['login', 'register'].map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setError('') }}
              style={{
                flex: 1,
                padding: '0.45rem',
                borderRadius: '7px',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: mode === m ? 'linear-gradient(135deg, #7c3aed, #6d28d9)' : 'transparent',
                color: mode === m ? '#fff' : 'var(--text-2)',
                boxShadow: mode === m ? '0 2px 8px rgba(124,58,237,0.35)' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              {m === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={labelStyle}>Email address</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
            />
          </div>
          <div>
            <label style={labelStyle}>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={mode === 'register' ? 'Min. 8 characters' : '••••••••'}
              required
            />
          </div>

          {error && (
            <div style={{
              background: 'rgba(244,63,94,0.1)',
              border: '1px solid rgba(244,63,94,0.25)',
              borderRadius: '8px',
              padding: '0.6rem 0.85rem',
              color: '#f87171',
              fontSize: '0.82rem',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
              color: '#fff',
              padding: '0.7rem',
              borderRadius: '10px',
              fontWeight: 600,
              fontSize: '0.9rem',
              marginTop: '0.25rem',
              boxShadow: '0 4px 16px rgba(124,58,237,0.35)',
              letterSpacing: '0.01em',
            }}
          >
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-3)', marginTop: '1.5rem' }}>
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            style={{ background: 'none', color: 'var(--accent)', fontWeight: 600, padding: 0, fontSize: '0.8rem' }}
          >
            {mode === 'login' ? 'Register' : 'Sign In'}
          </button>
        </p>
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  fontSize: '0.76rem',
  fontWeight: 600,
  color: 'var(--text-2)',
  marginBottom: '0.4rem',
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
}
