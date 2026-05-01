import { useState, useEffect, useRef } from 'react'
import * as api from '../api.js'

function formatDate(str) {
  if (!str) return ''
  try {
    const dt = new Date(str)
    if (isNaN(dt)) return str.slice(0, 10)
    const now = new Date()
    const diff = Math.floor((now - dt) / 86400000)
    if (diff === 0) return `Aujourd'hui ${dt.toLocaleTimeString('fr', { hour: '2-digit', minute: '2-digit' })}`
    if (diff === 1) return `Hier ${dt.toLocaleTimeString('fr', { hour: '2-digit', minute: '2-digit' })}`
    if (diff < 7) return dt.toLocaleDateString('fr', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
    return dt.toLocaleDateString('fr')
  } catch {
    return str.slice(0, 10)
  }
}

export default function ArticleList({ selection, selectedArticleId, onArticleSelect, onArticlesChange, onBack }) {
  const [articles, setArticles] = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)
  const debounceRef = useRef(null)

  useEffect(() => {
    setSearch('')
    loadArticles('')
  }, [selection])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => loadArticles(search), 300)
    return () => clearTimeout(debounceRef.current)
  }, [search])

  const loadArticles = async (q = search) => {
    setLoading(true)
    try {
      const params = {}
      if (selection.type === 'smart')      params.smart   = selection.value
      else if (selection.type === 'feed')  params.feed_id = selection.value
      if (q) params.search = q
      const data = await api.getArticles(params)
      setArticles(data)
    } finally {
      setLoading(false)
    }
  }

  const refresh = () => loadArticles()

  // Expose refresh to parent via callback
  useEffect(() => {
    if (onArticlesChange) onArticlesChange.current = refresh
  })

  const handleMarkAllRead = async () => {
    const feedId = selection.type === 'feed' ? selection.value : null
    await api.markAllRead(feedId)
    setArticles(prev => prev.map(a => ({ ...a, read_status: 1 })))
  }

  const handleToggleRead = async (e, article) => {
    e.stopPropagation()
    const updated = await api.patchArticle(article.id, { read_status: !article.read_status })
    setArticles(prev => prev.map(a => a.id === article.id ? { ...a, read_status: updated.read_status } : a))
  }

  const handleToggleFavorite = async (e, article) => {
    e.stopPropagation()
    const updated = await api.patchArticle(article.id, { favorite: !article.favorite })
    setArticles(prev => prev.map(a => a.id === article.id ? { ...a, favorite: updated.favorite } : a))
  }

  const handleSelect = async (article) => {
    onArticleSelect(article)
    if (!article.read_status) {
      await api.patchArticle(article.id, { read_status: true })
      setArticles(prev => prev.map(a => a.id === article.id ? { ...a, read_status: 1 } : a))
    }
  }

  const unreadCount = articles.filter(a => !a.read_status).length

  return (
    <div className="article-list">
      <div className="article-list-toolbar">
        {onBack && (
          <button className="btn icon mobile-back" onClick={onBack} title="Retour aux flux">‹</button>
        )}
        <input
          type="search"
          placeholder="Rechercher…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button className="btn" onClick={handleMarkAllRead} title="Tout marquer comme lu">✓ Lus</button>
      </div>
      <div className="article-count">
        {loading
          ? 'Chargement…'
          : `${articles.length} article${articles.length > 1 ? 's' : ''} · ${unreadCount} non lu${unreadCount > 1 ? 's' : ''}`
        }
      </div>
      <div className="article-items">
        {articles.map(article => (
          <div
            key={article.id}
            className={`article-item ${!article.read_status ? 'unread' : ''} ${article.favorite ? 'favorite' : ''} ${selectedArticleId === article.id ? 'active' : ''}`}
            onClick={() => handleSelect(article)}
          >
            <div className="article-item-title">{article.title || '(sans titre)'}</div>
            <div className="article-item-meta">
              {article.feed_name}
              {article.published_date || article.fetch_date
                ? ` · ${formatDate(article.published_date || article.fetch_date)}`
                : ''}
              <span style={{ float: 'right', display: 'flex', gap: 6 }}>
                <span
                  title={article.favorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
                  onClick={e => handleToggleFavorite(e, article)}
                  style={{ cursor: 'pointer' }}
                >
                  {article.favorite ? '⭐' : '☆'}
                </span>
                <span
                  title={article.read_status ? 'Marquer non lu' : 'Marquer lu'}
                  onClick={e => handleToggleRead(e, article)}
                  style={{ cursor: 'pointer' }}
                >
                  {article.read_status ? '✓' : '●'}
                </span>
              </span>
            </div>
          </div>
        ))}
        {!loading && articles.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center', color: '#7f8c8d', fontSize: 14 }}>
            Aucun article
          </div>
        )}
      </div>
    </div>
  )
}
