const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Token management ──────────────────────────────────────────────────────
export const getToken   = () => localStorage.getItem('rss_token')
export const setToken   = (t) => localStorage.setItem('rss_token', t)
export const clearToken = () => localStorage.removeItem('rss_token')

export function getUserFromToken() {
  const token = getToken()
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.exp * 1000 < Date.now()) { clearToken(); return null }
    return { id: parseInt(payload.sub), username: payload.username }
  } catch { clearToken(); return null }
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    clearToken()
    window.dispatchEvent(new Event('auth:logout'))
    throw new Error('Session expirée.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    let detail = body.detail
    if (Array.isArray(detail)) {
      detail = detail.map(e => (typeof e === 'object' ? e.msg : e)).filter(Boolean).join(' · ')
    }
    throw new Error(String(detail || `Erreur HTTP ${res.status}`))
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (body) => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// ── Auth ──────────────────────────────────────────────────────────────────
export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || 'Identifiants incorrects.')
  setToken(data.access_token)
  return data
}

export async function register(username, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || "Erreur lors de l'inscription.")
  setToken(data.access_token)
  return data
}

export function logout() { clearToken() }

// Feeds
export const getFeeds       = ()           => request('/feeds')
export const createFeed     = (data)       => request('/feeds', { method: 'POST', ...json(data) })
export const updateFeed     = (id, data)   => request(`/feeds/${id}`, { method: 'PUT', ...json(data) })
export const deleteFeed     = (id)         => request(`/feeds/${id}`, { method: 'DELETE' })
export const setFeedActive  = (id, active) => request(`/feeds/${id}/active`, { method: 'PATCH', ...json({ active }) })
export const refreshFeed    = (id)         => request(`/feeds/${id}/refresh`, { method: 'POST' })
export const refreshAll     = ()           => request('/refresh', { method: 'POST' })
export const discoverFeed   = (url)        => request('/feeds/discover', { method: 'POST', ...json({ url }) })

// Articles
export const getArticle     = (id)          => request(`/articles/${id}`)
export const getArticles    = (params = {}) => {
  const qs = new URLSearchParams()
  if (params.feed_id != null) qs.set('feed_id', params.feed_id)
  if (params.smart)           qs.set('smart', params.smart)
  if (params.search)          qs.set('search', params.search)
  return request(`/articles?${qs}`)
}
export const patchArticle   = (id, data)   => request(`/articles/${id}`, { method: 'PATCH', ...json(data) })
export const markAllRead    = (feed_id)    => {
  const qs = feed_id != null ? `?feed_id=${feed_id}` : ''
  return request(`/articles/mark-all-read${qs}`, { method: 'POST' })
}

// OPML
export async function exportOpml() {
  const res = await fetch(`${BASE}/opml/export`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error('Erreur export OPML')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'flux_rss.opml'; a.click()
  URL.revokeObjectURL(url)
}

export const importOpml = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request('/opml/import', { method: 'POST', body: form })
}
