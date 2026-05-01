import { useState } from 'react'
import * as api from '../api.js'

export default function LoginPage({ onLogin }) {
  const [mode, setMode]         = useState('login')  // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = mode === 'login'
        ? await api.login(username, password)
        : await api.register(username, password)
      onLogin(data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: '#f0f3f6', fontFamily: 'var(--font)',
    }}>
      <div style={{
        background: 'white', borderRadius: 10, padding: '36px 32px',
        width: 340, boxShadow: '0 4px 24px rgba(0,0,0,.12)',
      }}>
        <h1 style={{ fontSize: 22, marginBottom: 6, color: '#2c3e50', fontWeight: 700 }}>
          📰 RSS Reader
        </h1>
        <p style={{ fontSize: 13, color: '#7f8c8d', marginBottom: 24 }}>
          {mode === 'login' ? 'Connexion à votre compte' : 'Créer un compte'}
        </p>

        <form onSubmit={submit}>
          <div className="form-row">
            <label>Nom d'utilisateur</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
            />
          </div>
          <div className="form-row">
            <label>Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>

          {error && (
            <p style={{ color: '#e74c3c', fontSize: 13, margin: '8px 0 0' }}>{error}</p>
          )}

          <button
            type="submit"
            className="btn primary"
            style={{ width: '100%', marginTop: 16 }}
            disabled={loading}
          >
            {loading
              ? <span className="spin">⏳</span>
              : (mode === 'login' ? 'Se connecter' : "S'inscrire")}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 13, marginTop: 16, color: '#7f8c8d' }}>
          {mode === 'login' ? 'Pas encore de compte ?' : 'Déjà un compte ?'}
          {' '}
          <button
            style={{
              background: 'none', border: 'none', color: '#3498db',
              cursor: 'pointer', fontSize: 13, padding: 0,
            }}
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
          >
            {mode === 'login' ? "S'inscrire" : 'Se connecter'}
          </button>
        </p>
      </div>
    </div>
  )
}
