const BASE = (import.meta.env.VITE_API_URL ?? '') + '/api'

function getToken() {
  return localStorage.getItem('token')
}

function authHeaders() {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

function handleUnauthorized() {
  localStorage.removeItem('token')
  localStorage.removeItem('email')
  window.location.reload()
}

async function parseResponse(res) {
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error('Session expired')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`)
  return data
}

export async function apiGet(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  return parseResponse(res)
}

export async function apiPost(path, body, { skipAuthRedirect = false } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (skipAuthRedirect && res.status === 401) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Invalid credentials')
  }
  return parseResponse(res)
}

export async function apiDelete(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  })
  return parseResponse(res)
}
