const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (body) => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

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
export const exportOpmlUrl  = () => `${BASE}/opml/export`
export const importOpml     = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request('/opml/import', { method: 'POST', body: form })
}
