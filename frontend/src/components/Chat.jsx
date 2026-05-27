import { useEffect, useRef, useState } from 'react'
import { apiDelete, apiPost } from '../api.js'

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Hi! I'm your live events ticket assistant.\n\nTry asking:\n• \"Show me concerts near Charlotte in June\"\n• \"Any sports events in Miami this summer?\"\n• \"Subscribe me to Taylor Swift\"\n• \"List my subscriptions\"",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setMessages(prev => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      const data = await apiPost('/chat', { message: text })
      setMessages(prev => [...prev, { role: 'assistant', text: data.reply }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', text: `Error: ${err.message}`, isError: true }])
    } finally {
      setLoading(false)
    }
  }

  async function clearChat() {
    await apiDelete('/chat')
    setMessages([{ role: 'assistant', text: 'Conversation cleared. How can I help you?' }])
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      maxWidth: '760px',
      margin: '0 auto',
      width: '100%',
      padding: '0',
    }}>
      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '1.5rem 1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            className="fade-up"
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              gap: '0.6rem',
              alignItems: 'flex-end',
            }}
          >
            {/* Assistant avatar */}
            {msg.role === 'assistant' && (
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                flexShrink: 0,
                marginBottom: '2px',
                boxShadow: '0 4px 12px rgba(124,58,237,0.3)',
              }}>
                🎫
              </div>
            )}

            <div style={{
              maxWidth: '78%',
              padding: '0.75rem 1rem',
              borderRadius: msg.role === 'user'
                ? '18px 18px 4px 18px'
                : '4px 18px 18px 18px',
              background: msg.role === 'user'
                ? 'linear-gradient(135deg, #7c3aed, #6d28d9)'
                : msg.isError
                ? 'rgba(244,63,94,0.1)'
                : 'var(--surface-2)',
              border: msg.role === 'user'
                ? 'none'
                : msg.isError
                ? '1px solid rgba(244,63,94,0.25)'
                : '1px solid var(--border)',
              color: msg.role === 'user' ? '#fff' : msg.isError ? '#f87171' : 'var(--text)',
              boxShadow: msg.role === 'user'
                ? '0 4px 16px rgba(124,58,237,0.3)'
                : '0 2px 8px rgba(0,0,0,0.2)',
              fontSize: '0.88rem',
              lineHeight: '1.6',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              letterSpacing: '0.01em',
            }}>
              {msg.text}
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {loading && (
          <div className="fade-up" style={{ display: 'flex', alignItems: 'flex-end', gap: '0.6rem' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              flexShrink: 0,
              boxShadow: '0 4px 12px rgba(124,58,237,0.3)',
            }}>
              🎫
            </div>
            <div style={{
              padding: '0.8rem 1rem',
              borderRadius: '4px 18px 18px 18px',
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              display: 'flex',
              gap: '5px',
              alignItems: 'center',
            }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  animation: `pulse-dot 1.2s ease-in-out ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--surface)',
        padding: '0.85rem 1.25rem',
        display: 'flex',
        gap: '0.6rem',
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Ask about events, prices, or subscriptions… (Enter to send)"
          disabled={loading}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            borderRadius: '10px',
            padding: '0.65rem 0.9rem',
            fontSize: '0.88rem',
            lineHeight: '1.5',
            maxHeight: '120px',
            overflowY: 'auto',
            background: 'var(--surface-2)',
          }}
          onInput={e => {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
          }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            background: 'linear-gradient(135deg, #7c3aed, #6d28d9)',
            color: '#fff',
            padding: '0.65rem 1.15rem',
            flexShrink: 0,
            borderRadius: '10px',
            fontWeight: 600,
            boxShadow: '0 4px 12px rgba(124,58,237,0.35)',
            fontSize: '0.85rem',
          }}
        >
          Send
        </button>
        <button
          onClick={clearChat}
          title="Clear conversation"
          style={{
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            color: 'var(--text-3)',
            padding: '0.65rem 0.75rem',
            flexShrink: 0,
            borderRadius: '10px',
            fontSize: '0.85rem',
          }}
        >
          🗑
        </button>
      </div>
    </div>
  )
}
