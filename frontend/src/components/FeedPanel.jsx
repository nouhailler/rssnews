import { useState } from 'react'
import * as api from '../api.js'

const SMART_ITEMS = [
  { key: 'all',       label: 'Tous les articles', icon: '📰' },
  { key: 'unread',    label: 'Non lus',            icon: '🔵' },
  { key: 'favorites', label: 'Favoris',            icon: '⭐' },
]

export default function FeedPanel({ feeds, selection, onSelect, onFeedsChange, onAddFeed, onRefreshAll, isRefreshing }) {
  const unreadTotal = feeds.reduce((s, f) => s + (f.unread_count || 0), 0)

  const byCategory = feeds.reduce((acc, f) => {
    ;(acc[f.category] = acc[f.category] || []).push(f)
    return acc
  }, {})

  const isActive = (type, value) =>
    selection.type === type && selection.value === value

  const handleDeleteFeed = async (e, feed) => {
    e.stopPropagation()
    if (!confirm(`Supprimer le flux « ${feed.name} » et tous ses articles ?`)) return
    await api.deleteFeed(feed.id)
    onFeedsChange()
  }

  const handleRefreshFeed = async (e, feed) => {
    e.stopPropagation()
    await api.refreshFeed(feed.id)
    onFeedsChange()
  }

  const handleMarkAllRead = async (e, feedId) => {
    e.stopPropagation()
    await api.markAllRead(feedId)
    onFeedsChange()
    onSelect({ type: 'feed', value: feedId })
  }

  return (
    <div className="feed-panel">
      <div className="feed-panel-header">
        <span>Flux RSS</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className="btn icon" onClick={onAddFeed} title="Ajouter un flux">＋</button>
          <button className="btn icon" onClick={onRefreshAll} disabled={isRefreshing} title="Tout rafraîchir">
            <span className={isRefreshing ? 'spin' : ''}>🔄</span>
          </button>
        </div>
      </div>

      <div className="feed-list">
        {SMART_ITEMS.map(({ key, label, icon }) => (
          <div
            key={key}
            className={`feed-item ${isActive('smart', key) ? 'active' : ''}`}
            onClick={() => onSelect({ type: 'smart', value: key })}
          >
            <span>{icon} {label}</span>
            {key === 'all' && unreadTotal > 0 && (
              <span className="feed-badge">{unreadTotal}</span>
            )}
            {key === 'unread' && unreadTotal > 0 && (
              <span className="feed-badge">{unreadTotal}</span>
            )}
          </div>
        ))}

        {Object.keys(byCategory).sort().map(cat => (
          <div key={cat}>
            <div className="feed-item category">{cat}</div>
            {byCategory[cat].sort((a, b) => a.name.localeCompare(b.name)).map(feed => (
              <FeedRow
                key={feed.id}
                feed={feed}
                active={isActive('feed', feed.id)}
                onClick={() => onSelect({ type: 'feed', value: feed.id })}
                onDelete={(e) => handleDeleteFeed(e, feed)}
                onRefresh={(e) => handleRefreshFeed(e, feed)}
                onMarkAllRead={(e) => handleMarkAllRead(e, feed.id)}
                onEdit={() => onAddFeed(feed)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function FeedRow({ feed, active, onClick, onDelete, onRefresh, onMarkAllRead, onEdit }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div
      className={`feed-item feed ${active ? 'active' : ''} ${feed.fetch_error ? 'error' : ''} ${!feed.active ? 'inactive' : ''}`}
      onClick={onClick}
      title={feed.fetch_error || feed.name}
    >
      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {feed.fetch_error ? '⚠ ' : '📄 '}{feed.name}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
        {feed.unread_count > 0 && <span className="feed-badge">{feed.unread_count}</span>}
        <div style={{ position: 'relative' }}>
          <button
            className="btn icon"
            style={{ padding: '1px 5px', fontSize: 12, lineHeight: 1 }}
            onClick={e => { e.stopPropagation(); setMenuOpen(v => !v) }}
            title="Options"
          >⋯</button>
          {menuOpen && (
            <ContextMenu
              onClose={() => setMenuOpen(false)}
              items={[
                { label: '🔄 Rafraîchir', action: (e) => { onRefresh(e); setMenuOpen(false) } },
                { label: '✓ Tout marquer lu', action: (e) => { onMarkAllRead(e); setMenuOpen(false) } },
                { label: '✏️ Modifier', action: (e) => { e.stopPropagation(); onEdit(); setMenuOpen(false) } },
                { label: '🗑 Supprimer', action: (e) => { onDelete(e); setMenuOpen(false) }, danger: true },
              ]}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function ContextMenu({ items, onClose }) {
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 9 }} onClick={onClose} />
      <div style={{
        position: 'absolute', right: 0, top: '100%', zIndex: 10,
        background: 'white', border: '1px solid #e0e4e8', borderRadius: 6,
        boxShadow: '0 4px 16px rgba(0,0,0,.15)', minWidth: 160, overflow: 'hidden',
      }}>
        {items.map(({ label, action, danger }) => (
          <div
            key={label}
            onClick={action}
            style={{
              padding: '8px 14px', cursor: 'pointer', fontSize: 13,
              color: danger ? '#e74c3c' : '#2c3e50',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#f0f7ff'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {label}
          </div>
        ))}
      </div>
    </>
  )
}
