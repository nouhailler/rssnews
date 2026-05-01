import { useState, useEffect, useRef } from 'react'
import * as api from '../api.js'

function sanitizeHtml(html) {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/\s+on\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\s+on\w+\s*=\s*'[^']*'/gi, '')
    .replace(/href\s*=\s*"javascript:[^"]*"/gi, 'href="#"')
}

function stripHtml(html) {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
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
  const [article, setArticle]   = useState(null)
  const [fontSize, setFontSize] = useState(15)
  const [ttsState, setTtsState] = useState('idle')   // idle | playing | paused
  const [ttsSpeed, setTtsSpeed] = useState(1.0)
  const ttsRef = useRef(null)

  useEffect(() => {
    if (articleId == null) { setArticle(null); ttsStop(); return }
    fetchArticle(articleId)
  }, [articleId])

  // Arrête la lecture quand on change d'article
  useEffect(() => { return () => window.speechSynthesis?.cancel() }, [])

  const fetchArticle = async (id) => {
    ttsStop()
    const data = await fetch(
      `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/articles/${id}`
    ).then(r => r.json())
    setArticle(data)
    const text = ((data.title || '') + '. ' + (data.content || data.summary || '')).trim()
    onTtsTextChange(text)
  }

  // ── TTS ──────────────────────────────────────────────────────────────
  const ttsPlay = (textOverride) => {
    if (!('speechSynthesis' in window)) return
    const raw = textOverride || (article ? (article.title || '') + '. ' + (article.content || article.summary || '') : '')
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(stripHtml(raw))
    utt.lang  = 'fr-FR'
    utt.rate  = ttsSpeed
    utt.onend = () => setTtsState('idle')
    utt.onerror = () => setTtsState('idle')
    ttsRef.current = utt
    window.speechSynthesis.speak(utt)
    setTtsState('playing')
  }

  const ttsPause  = () => { window.speechSynthesis.pause();  setTtsState('paused')  }
  const ttsResume = () => { window.speechSynthesis.resume(); setTtsState('playing') }
  const ttsStop   = () => { window.speechSynthesis?.cancel(); setTtsState('idle')   }

  const handleSpeedChange = (e) => {
    const v = parseFloat(e.target.value)
    setTtsSpeed(v)
    if (ttsState === 'playing') { ttsStop(); setTimeout(() => ttsPlay(), 80) }
  }

  // ── Actions article ──────────────────────────────────────────────────
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

  // ── Rendu vide ───────────────────────────────────────────────────────
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
  const metaParts  = [article.feed_name, article.author, formatDate(article.published_date || article.fetch_date)].filter(Boolean)
  const ttsSupported = 'speechSynthesis' in window

  return (
    <div className="article-view">

      {/* Barre d'actions */}
      <div className="article-view-bar">
        {onBack && (
          <button className="btn icon mobile-back" onClick={onBack} title="Retour">‹ Retour</button>
        )}
        <button className={`btn ${article.favorite ? 'active' : ''}`} onClick={toggleFavorite}>
          {article.favorite ? '⭐' : '☆'}
        </button>
        <button className={`btn ${article.read_status ? 'active' : ''}`} onClick={toggleRead}>
          {article.read_status ? '✓ Lu' : '● Non lu'}
        </button>
        {article.link && (
          <button className="btn" onClick={() => window.open(article.link, '_blank', 'noopener')}>
            🌐
          </button>
        )}
        <span style={{ flex: 1 }} />
        <button className="btn icon" onClick={() => setFontSize(s => Math.max(10, s - 1))}>A-</button>
        <button className="btn icon" onClick={() => setFontSize(s => Math.min(26, s + 1))}>A+</button>
      </div>

      {/* Barre TTS intégrée — visible sur toutes les tailles */}
      {ttsSupported && (
        <div className="article-tts-bar">
          <span className="tts-bar-label">🔊</span>
          {ttsState === 'idle'   && <button className="btn" onClick={() => ttsPlay()}>▶ Lire</button>}
          {ttsState === 'playing' && <button className="btn" onClick={ttsPause}>⏸ Pause</button>}
          {ttsState === 'paused'  && <button className="btn" onClick={ttsResume}>▶ Reprendre</button>}
          {ttsState !== 'idle'   && <button className="btn" onClick={ttsStop}>⏹ Stop</button>}
          {ttsState === 'playing' && <span className="spin" style={{ fontSize: 14 }}>🎙</span>}
          <span style={{ flex: 1 }} />
          <select className="tts-speed" value={ttsSpeed} onChange={handleSpeedChange}>
            {[0.75, 1.0, 1.25, 1.5, 1.75, 2.0].map(v => (
              <option key={v} value={v}>{v}×</option>
            ))}
          </select>
        </div>
      )}

      {/* Contenu */}
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
