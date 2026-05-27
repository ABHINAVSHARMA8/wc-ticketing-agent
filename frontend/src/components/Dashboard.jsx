import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost } from '../api.js'

const NOTIFY_LABELS = { any: 'Any change', drop: 'Drop only', rise: 'Rise only' }

const CATEGORY_COLORS = {
  music:  { bg: 'rgba(124,58,237,0.15)', color: '#a78bfa', border: 'rgba(124,58,237,0.3)' },
  sports: { bg: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: 'rgba(59,130,246,0.3)' },
  arts:   { bg: 'rgba(236,72,153,0.15)', color: '#f472b6', border: 'rgba(236,72,153,0.3)' },
}

function categoryStyle(cat) {
  return CATEGORY_COLORS[(cat || '').toLowerCase()] || { bg: 'rgba(255,255,255,0.05)', color: 'var(--text-3)', border: 'rgba(255,255,255,0.1)' }
}

export default function Dashboard() {
  const [subscriptions, setSubscriptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [removing, setRemoving] = useState(null)

  const [location, setLocation] = useState('')
  const [dateFrom, setDateFrom] = useState('2026-06-01')
  const [dateTo, setDateTo] = useState('2026-08-31')
  const [maxPrice, setMaxPrice] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [selected, setSelected] = useState([])
  const [notifyOn, setNotifyOn] = useState('any')
  const [threshold, setThreshold] = useState('')
  const [subscribing, setSubscribing] = useState(false)
  const [subscribeMsg, setSubscribeMsg] = useState('')

  useEffect(() => { fetchSubscriptions() }, [])

  async function fetchSubscriptions() {
    setLoading(true)
    setError('')
    try {
      setSubscriptions(await apiGet('/subscriptions'))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function unsubscribe(matchId) {
    setRemoving(matchId)
    try {
      await apiDelete('/subscriptions', { match_ids: [matchId] })
      setSubscriptions(prev => prev.filter(s => s.match_id !== matchId))
    } finally {
      setRemoving(null)
    }
  }

  async function searchMatches() {
    if (!location.trim()) { setSearchError('Enter a location'); return }
    setSearching(true)
    setSearchError('')
    setSearchResults(null)
    setSelected([])
    setSubscribeMsg('')
    try {
      const params = new URLSearchParams({ location, date_from: dateFrom, date_to: dateTo })
      if (maxPrice) params.set('max_price', maxPrice)
      setSearchResults(await apiGet(`/matches?${params}`))
    } catch (err) {
      setSearchError(err.message)
    } finally {
      setSearching(false)
    }
  }

  function toggleSelect(id) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  async function subscribeSelected() {
    if (!selected.length) return
    setSubscribing(true)
    setSubscribeMsg('')
    try {
      const body = {
        match_ids: selected,
        notify_on: notifyOn,
        ...(threshold ? { price_threshold: parseFloat(threshold) } : {}),
      }
      const data = await apiPost('/subscriptions', body)
      setSubscribeMsg(`Subscribed to ${data.subscribed.length} event(s).`)
      setSelected([])
      fetchSubscriptions()
    } catch (err) {
      setSubscribeMsg(`Error: ${err.message}`)
    } finally {
      setSubscribing(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', background: 'var(--bg)' }}>

      {/* ── Left: Active subscriptions ───────────────────── */}
      <div style={{
        width: '320px',
        flexShrink: 0,
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface)',
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '1rem 1.1rem',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <h2 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.01em' }}>
              Active Alerts
            </h2>
            {subscriptions.length > 0 && (
              <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginTop: '0.1rem' }}>
                {subscriptions.length} subscription{subscriptions.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <button
            onClick={fetchSubscriptions}
            style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              color: 'var(--text-2)',
              padding: '0.3rem 0.65rem',
              fontSize: '0.75rem',
              borderRadius: '8px',
            }}
          >
            Refresh
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
          {loading && (
            <p style={{ color: 'var(--text-3)', fontSize: '0.83rem', textAlign: 'center', marginTop: '1.5rem' }}>
              Loading…
            </p>
          )}
          {error && (
            <p style={{ color: 'var(--red)', fontSize: '0.82rem', padding: '0.5rem' }}>{error}</p>
          )}
          {!loading && !error && subscriptions.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: '2.5rem', padding: '0 1rem' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem', opacity: 0.4 }}>🔔</div>
              <p style={{ color: 'var(--text-3)', fontSize: '0.82rem', lineHeight: 1.6 }}>
                No active subscriptions.<br />Search for events on the right.
              </p>
            </div>
          )}
          {subscriptions.map(sub => (
            <div key={sub.id} className="fade-up" style={{
              border: '1px solid var(--border)',
              borderRadius: '12px',
              padding: '0.85rem',
              marginBottom: '0.6rem',
              background: 'var(--surface-2)',
              transition: 'border-color 0.15s',
            }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.2rem', color: 'var(--text)', lineHeight: 1.3 }}>
                {sub.teams}
              </div>
              <div style={{ color: 'var(--text-3)', fontSize: '0.76rem', marginBottom: '0.6rem' }}>
                {sub.venue}, {sub.city} · {sub.date}
              </div>
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
                <Badge variant="default">{NOTIFY_LABELS[sub.notify_on] || sub.notify_on}</Badge>
                {sub.price_threshold && <Badge variant="yellow">Below ${sub.price_threshold}</Badge>}
                <Badge variant="default">Last: ${sub.last_price}</Badge>
              </div>
              <button
                onClick={() => unsubscribe(sub.match_id)}
                disabled={removing === sub.match_id}
                style={{
                  background: 'rgba(244,63,94,0.08)',
                  border: '1px solid rgba(244,63,94,0.2)',
                  color: '#f87171',
                  padding: '0.3rem 0.65rem',
                  fontSize: '0.76rem',
                  width: '100%',
                  borderRadius: '7px',
                }}
              >
                {removing === sub.match_id ? 'Removing…' : 'Unsubscribe'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right: Search + results ──────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', background: 'var(--bg)' }}>

        {/* Search form */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '14px',
          padding: '1.25rem',
          marginBottom: '1.25rem',
        }}>
          <h2 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text)', marginBottom: '1rem', letterSpacing: '-0.01em' }}>
            Search Events
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={labelStyle}>Location</label>
              <input
                placeholder="e.g. Charlotte, NC"
                value={location}
                onChange={e => setLocation(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && searchMatches()}
              />
            </div>
            <div>
              <label style={labelStyle}>From</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>To</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={labelStyle}>Max Price (USD)</label>
              <input type="number" placeholder="No limit" value={maxPrice} onChange={e => setMaxPrice(e.target.value)} />
            </div>
          </div>
          <button
            onClick={searchMatches}
            disabled={searching}
            style={{
              background: 'linear-gradient(135deg, #7c3aed, #6d28d9)',
              color: '#fff',
              width: '100%',
              padding: '0.65rem',
              fontWeight: 600,
              borderRadius: '10px',
              boxShadow: '0 4px 12px rgba(124,58,237,0.3)',
              fontSize: '0.875rem',
            }}
          >
            {searching ? 'Searching…' : 'Search'}
          </button>
          {searchError && (
            <p style={{ color: 'var(--red)', fontSize: '0.8rem', marginTop: '0.6rem' }}>{searchError}</p>
          )}
        </div>

        {/* Results */}
        {searchResults !== null && (
          <div className="fade-up">
            {searchResults.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-3)', fontSize: '0.85rem' }}>
                No events found for your criteria.
              </div>
            ) : (
              <>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-3)', marginBottom: '0.75rem', fontWeight: 500 }}>
                  {searchResults.length} event{searchResults.length !== 1 ? 's' : ''} found · click to select
                </p>

                {searchResults.map(m => {
                  const isSelected = selected.includes(m.id)
                  const cs = categoryStyle(m.category)
                  return (
                    <div
                      key={m.id}
                      onClick={() => toggleSelect(m.id)}
                      style={{
                        border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                        borderRadius: '12px',
                        padding: '0.9rem 1rem',
                        marginBottom: '0.6rem',
                        background: isSelected ? 'rgba(124,58,237,0.08)' : 'var(--surface)',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '0.75rem',
                        boxShadow: isSelected ? '0 0 0 1px var(--accent)' : 'none',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.87rem', color: 'var(--text)' }}>{m.title}</span>
                          {m.category && (
                            <span style={{
                              fontSize: '0.68rem',
                              fontWeight: 600,
                              padding: '0.15rem 0.5rem',
                              borderRadius: '99px',
                              background: cs.bg,
                              color: cs.color,
                              border: `1px solid ${cs.border}`,
                              textTransform: 'capitalize',
                              letterSpacing: '0.03em',
                              flexShrink: 0,
                            }}>
                              {m.category}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.77rem', color: 'var(--text-3)' }}>
                          {m.venue}, {m.city}
                        </div>
                        <div style={{ fontSize: '0.77rem', color: 'var(--text-3)', marginTop: '0.1rem' }}>
                          {m.date} · {m.distance_miles} mi away
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        {m.price_usd ? (
                          <div style={{ fontWeight: 700, fontSize: '1.05rem', color: isSelected ? 'var(--accent)' : 'var(--text)' }}>
                            ${m.price_usd}
                          </div>
                        ) : (
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>TBD</div>
                        )}
                        <div style={{ fontSize: '0.72rem', color: isSelected ? 'var(--accent)' : 'var(--text-3)', marginTop: '0.2rem' }}>
                          {isSelected ? '✓ Selected' : 'Select'}
                        </div>
                      </div>
                    </div>
                  )
                })}

                {/* Subscribe panel */}
                {selected.length > 0 && (
                  <div className="fade-up" style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '14px',
                    padding: '1.1rem',
                    marginTop: '0.75rem',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
                  }}>
                    <p style={{ fontWeight: 700, fontSize: '0.87rem', marginBottom: '0.85rem', color: 'var(--text)' }}>
                      Subscribe to {selected.length} selected event{selected.length !== 1 ? 's' : ''}
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.85rem' }}>
                      <div>
                        <label style={labelStyle}>Notify On</label>
                        <select value={notifyOn} onChange={e => setNotifyOn(e.target.value)}>
                          <option value="any">Any price change</option>
                          <option value="drop">Price drop only</option>
                          <option value="rise">Price rise only</option>
                        </select>
                      </div>
                      <div>
                        <label style={labelStyle}>Alert below price</label>
                        <input type="number" placeholder="e.g. 300 (optional)" value={threshold} onChange={e => setThreshold(e.target.value)} />
                      </div>
                    </div>
                    <button
                      onClick={subscribeSelected}
                      disabled={subscribing}
                      style={{
                        background: 'linear-gradient(135deg, #10b981, #059669)',
                        color: '#fff',
                        width: '100%',
                        padding: '0.65rem',
                        fontWeight: 600,
                        borderRadius: '10px',
                        boxShadow: '0 4px 12px rgba(16,185,129,0.3)',
                        fontSize: '0.875rem',
                      }}
                    >
                      {subscribing ? 'Subscribing…' : `Subscribe to ${selected.length} event${selected.length !== 1 ? 's' : ''}`}
                    </button>
                    {subscribeMsg && (
                      <p style={{
                        fontSize: '0.81rem',
                        color: subscribeMsg.startsWith('Error') ? 'var(--red)' : 'var(--green)',
                        marginTop: '0.6rem',
                        fontWeight: 500,
                      }}>
                        {subscribeMsg}
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  fontSize: '0.72rem',
  fontWeight: 600,
  color: 'var(--text-3)',
  marginBottom: '0.4rem',
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
}

function Badge({ children, variant = 'default' }) {
  const styles = {
    default: { bg: 'rgba(255,255,255,0.05)', color: 'var(--text-3)', border: 'var(--border)' },
    yellow:  { bg: 'rgba(245,158,11,0.1)',   color: '#fbbf24',        border: 'rgba(245,158,11,0.25)' },
    green:   { bg: 'rgba(16,185,129,0.1)',   color: '#34d399',        border: 'rgba(16,185,129,0.25)' },
  }
  const s = styles[variant] || styles.default
  return (
    <span style={{
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.border}`,
      borderRadius: '5px',
      padding: '0.15rem 0.45rem',
      fontSize: '0.72rem',
      fontWeight: 500,
    }}>
      {children}
    </span>
  )
}
