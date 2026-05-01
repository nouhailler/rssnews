import { useState, useEffect, useRef, useCallback } from 'react'
import FeedPanel   from './components/FeedPanel.jsx'
import ArticleList from './components/ArticleList.jsx'
import ArticleView from './components/ArticleView.jsx'
import TTSBar      from './components/TTSBar.jsx'
import * as api    from './api.js'

// ---------------------------------------------------------------------------
// Modal — Ajouter / Modifier un flux
// ---------------------------------------------------------------------------
function FeedModal({ feed, categories, onClose, onSaved }) {
  const [url, setUrl]         = useState(feed?.url || '')
  const [name, setName]       = useState(feed?.name || '')
  const [category, setCategory] = useState(feed?.category || 'Général')
  const [hint, setHint]       = useState({ msg: '', type: '' })
  const [detecting, setDetecting] = useState(false)

  const detect = async () => {
    if (!url) return
    setDetecting(true)
    setHint({ msg: 'Vérification…', type: '' })
    try {
      const res = await api.discoverFeed(url).catch(async () => {
        // fallback: treat url as direct feed
        return null
      })
      if (res) {
        setHint({ msg: `Flux détecté : « ${res.title || url} »`, type: 'ok' })
        if (!name) setName(res.title || '')
        if (!url.includes(res.url)) setUrl(res.url)
      } else {
        setHint({ msg: 'URL utilisée directement comme flux.', type: 'ok' })
      }
    } catch (err) {
      setHint({ msg: err.message, type: 'err' })
    } finally {
      setDetecting(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!url) return
    try {
      if (feed) {
        await api.updateFeed(feed.id, { name: name || url, url, category })
      } else {
        await api.createFeed({ name: name || url, url, category })
      }
      onSaved()
      onClose()
    } catch (err) {
      setHint({ msg: err.message, type: 'err' })
    }
  }

  const allCategories = [...new Set([...categories, 'Général', category].filter(Boolean))]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>{feed ? 'Modifier le flux' : 'Ajouter un flux RSS'}</h2>
        <form onSubmit={submit}>
          <div className="form-row">
            <label>URL du flux</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="url"
                value={url}
                onChange={e => { setUrl(e.target.value); setHint({ msg: '', type: '' }) }}
                placeholder="https://example.com/feed.rss"
                required
                autoFocus
              />
              <button type="button" className="btn" onClick={detect} disabled={detecting || !url}>
                {detecting ? <span className="spin">⏳</span> : 'Détecter'}
              </button>
            </div>
            {hint.msg && <span className={`form-hint ${hint.type}`}>{hint.msg}</span>}
          </div>
          <div className="form-row">
            <label>Nom</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Nom affiché (auto si vide)"
            />
          </div>
          <div className="form-row">
            <label>Catégorie</label>
            <input
              list="cats"
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="Général"
            />
            <datalist id="cats">
              {allCategories.map(c => <option key={c} value={c} />)}
            </datalist>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={onClose}>Annuler</button>
            <button type="submit" className="btn primary">{feed ? 'Enregistrer' : 'Ajouter'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal — Import OPML
// ---------------------------------------------------------------------------
function OpmlModal({ onClose, onImported }) {
  const [file, setFile]       = useState(null)
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    try {
      const res = await api.importOpml(file)
      setResult(res)
      onImported()
    } catch (err) {
      setResult({ error: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Importer des flux (OPML)</h2>
        <form onSubmit={submit}>
          <div className="form-row">
            <label>Fichier OPML</label>
            <input type="file" accept=".opml,.xml" onChange={e => setFile(e.target.files[0])} required />
          </div>
          {result && !result.error && (
            <p style={{ color: '#27ae60', margin: '8px 0' }}>
              ✓ {result.added} flux importé{result.added > 1 ? 's' : ''} sur {result.found} trouvé{result.found > 1 ? 's' : ''}
            </p>
          )}
          {result?.error && <p style={{ color: '#e74c3c', margin: '8px 0' }}>✗ {result.error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn" onClick={onClose}>Fermer</button>
            <button type="submit" className="btn primary" disabled={loading || !file}>
              {loading ? <span className="spin">⏳</span> : 'Importer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
export default function App() {
  const [feeds, setFeeds]               = useState([])
  const [selection, setSelection]       = useState({ type: 'smart', value: 'all' })
  const [selectedArticleId, setSelectedArticleId] = useState(null)
  const [ttsText, setTtsText]           = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshMsg, setRefreshMsg]     = useState('')
  const [modal, setModal]               = useState(null)  // null | 'add-feed' | 'edit-feed' | 'opml'
  const [editFeed, setEditFeed]         = useState(null)

  const articleListRefreshRef = useRef(null)

  const loadFeeds = useCallback(async () => {
    const data = await api.getFeeds()
    setFeeds(data)
  }, [])

  useEffect(() => { loadFeeds() }, [])

  const handleRefreshAll = async () => {
    setIsRefreshing(true)
    setRefreshMsg('Mise à jour…')
    try {
      const report = await api.refreshAll()
      await loadFeeds()
      articleListRefreshRef.current?.()
      const errors = report.results.filter(r => !r.success).length
      setRefreshMsg(
        `${report.total_new} nouvel${report.total_new > 1 ? 's' : ''} article${report.total_new > 1 ? 's' : ''}` +
        (errors ? ` · ${errors} erreur${errors > 1 ? 's' : ''}` : '')
      )
    } catch (err) {
      setRefreshMsg('Erreur : ' + err.message)
    } finally {
      setIsRefreshing(false)
      setTimeout(() => setRefreshMsg(''), 5000)
    }
  }

  const handleFeedsChange = async () => {
    await loadFeeds()
    articleListRefreshRef.current?.()
  }

  const handleOpenAddFeed = (feedToEdit = null) => {
    setEditFeed(feedToEdit)
    setModal('add-feed')
  }

  const categories = [...new Set(feeds.map(f => f.category))]

  return (
    <div className="app">
      {/* Toolbar */}
      <div className="toolbar">
        <span className="toolbar-title">📰 RSS Reader</span>
        <button className="btn" style={{ color: 'white', borderColor: '#456', background: 'transparent' }} onClick={() => setModal('opml')}>
          OPML
        </button>
        <a href={api.exportOpmlUrl()} download="flux_rss.opml" style={{ color: 'white', fontSize: 13, textDecoration: 'none' }}>
          <button className="btn" style={{ color: 'white', borderColor: '#456', background: 'transparent' }}>⬇ Export</button>
        </a>
        <span className="toolbar-sep" />
        {refreshMsg && <span className="toolbar-status">{refreshMsg}</span>}
      </div>

      {/* Body */}
      <div className="app-body">
        <FeedPanel
          feeds={feeds}
          selection={selection}
          onSelect={setSelection}
          onFeedsChange={handleFeedsChange}
          onAddFeed={handleOpenAddFeed}
          onRefreshAll={handleRefreshAll}
          isRefreshing={isRefreshing}
        />
        <ArticleList
          selection={selection}
          selectedArticleId={selectedArticleId}
          onArticleSelect={(article) => setSelectedArticleId(article.id)}
          onArticlesChange={articleListRefreshRef}
        />
        <ArticleView
          articleId={selectedArticleId}
          onArticleUpdate={handleFeedsChange}
          onTtsTextChange={setTtsText}
        />
      </div>

      {/* TTS Bar */}
      <TTSBar text={ttsText} />

      {/* Modals */}
      {modal === 'add-feed' && (
        <FeedModal
          feed={editFeed}
          categories={categories}
          onClose={() => { setModal(null); setEditFeed(null) }}
          onSaved={handleFeedsChange}
        />
      )}
      {modal === 'opml' && (
        <OpmlModal
          onClose={() => setModal(null)}
          onImported={handleFeedsChange}
        />
      )}
    </div>
  )
}
