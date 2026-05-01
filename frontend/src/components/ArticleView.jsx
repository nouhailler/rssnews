import { useState, useEffect } from 'react'
import * as api from '../api.js'

function sanitizeHtml(html) {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/\s+on\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\s+on\w+\s*=\s*'[^']*'/gi, '')
    .replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"')
}

function formatDate(str) {
  if (!str) return ''
  try {
    return new Date(str).toLocaleDateString('fr', {
      day: '2-digit', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return str.slice(0, 16) }
}

export default function ArticleView({ articleId, onArticleUpdate, onTtsTextChange, onBack }) {
  const [article, setArticle] = useState(null)
  const [fontSize, setFontSize] = useState(15)

  useEffect(() => {
    if (articleId == null) { setArticle(null); return }
    api.getArticles().then(() => {})  // no-op
    // We already have the article data from the list — fetch full record for content
    fetchArticle(articleId)
  }, [articleId])

  const fetchArticle = async (id) => {
    const data = await fetch(
      `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/articles/${id}`
    ).then(r => r.json())
    setArticle(data)
    const text = ((data.title || '') + '. ' + (data.content || data.summary || '')).trim()
    onTtsTextChange(text)
  }

  const toggleFavorite = async () => {
    const updated = await api.patchArticle(article.id, { favorite: !article.favorite })
    setArticle(updated)
    onArticleUpdate?.(updated)
  }

  const toggleRead = async () => {
    const updated = await api.patchArticle(article.id, { read_status: !article.read_status })
    setArticle(updated)
    onArticleUpdate?.(updated)
  }

  if (!articleId) {
    return (
      <div className="article-view">
        <div className="article-view-empty">Sélectionnez un article pour le lire</div>
      </div>
    )
  }

  if (!article) {
    return (
      <div className="article-view">
        <div className="article-view-empty"><span className="spin">⏳</span> Chargement…</div>
      </div>
    )
  }

  const rawContent = article.content || article.summary || ''
  const looksHtml  = rawContent.includes('<') && rawContent.includes('>')
  const bodyHtml   = looksHtml ? sanitizeHtml(rawContent) : rawContent.split('\n\n').map(p => `<p>${p}</p>`).join('')

  const metaParts = [article.feed_name, article.author, formatDate(article.published_date || article.fetch_date)].filter(Boolean)

  return (
    <div className="article-view">
      <div className="article-view-bar">
        {onBack && (
          <button className="btn icon mobile-back" onClick={onBack} title="Retour">‹ Retour</button>
        )}
        <button
          className={`btn ${article.favorite ? 'active' : ''}`}
          onClick={toggleFavorite}
          title="Favori"
        >
          {article.favorite ? '⭐ Favori' : '☆ Favori'}
        </button>
        <button
          className={`btn ${article.read_status ? 'active' : ''}`}
          onClick={toggleRead}
          title="Marquer lu / non lu"
        >
          {article.read_status ? '✓ Lu' : '● Non lu'}
        </button>
        {article.link && (
          <button
            className="btn"
            onClick={() => window.open(article.link, '_blank', 'noopener')}
            title="Ouvrir dans le navigateur"
          >
            🌐 Ouvrir
          </button>
        )}
        <span style={{ flex: 1 }} />
        <button className="btn icon" onClick={() => setFontSize(s => Math.max(10, s - 1))} title="Réduire">A-</button>
        <button className="btn icon" onClick={() => setFontSize(s => Math.min(26, s + 1))} title="Agrandir">A+</button>
      </div>

      <div className="article-view-body">
        <h1 className="article-title">{article.title || '(sans titre)'}</h1>
        <div className="article-meta">{metaParts.join(' · ')}</div>
        {bodyHtml ? (
          <div
            className="article-content"
            style={{ fontSize }}
            dangerouslySetInnerHTML={{ __html: bodyHtml }}
          />
        ) : (
          <p style={{ color: '#7f8c8d', fontStyle: 'italic' }}>Aucun contenu disponible.</p>
        )}
        {article.link && (
          <div className="article-source-link">
            <a href={article.link} target="_blank" rel="noopener noreferrer">
              Lire l'article sur le site original →
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
