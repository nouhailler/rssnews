# CONTEXT.md — État du projet RSS Reader

Fichier de contexte pour reprendre le travail en session future.

---

## Vue d'ensemble

Le projet contient **deux versions indépendantes et coexistantes** du lecteur RSS :

| Version | Dossier | Stack | Usage |
|---------|---------|-------|-------|
| **Desktop** | racine (`main.py`, `ui/`, `tts/`) | Python + PyQt6 + Piper TTS | Linux uniquement |
| **Web** | `backend/` + `frontend/` | FastAPI + React + Web Speech API | Navigateur, mobile |

---

## Structure du dépôt

```
rssnews/
├── main.py              ← App desktop (PyQt6) — inchangée
├── database.py          ← DB desktop (séparée de la web)
├── rss_fetcher.py       ← Fetcher desktop
├── ui/                  ← Interface Qt
├── tts/                 ← Piper TTS offline
├── install.sh           ← Installeur Linux
│
├── backend/             ← API FastAPI (version web)
│   ├── main.py          ← Routes REST + auth
│   ├── database.py      ← SQLite multi-utilisateurs
│   ├── auth.py          ← JWT (python-jose) + bcrypt
│   ├── rss_fetcher.py   ← Même logique que desktop
│   ├── requirements.txt
│   └── render.yaml      ← Config déploiement Render
│
└── frontend/            ← Interface React (Vite)
    └── src/
        ├── App.jsx              ← Gestion auth + layout
        ├── api.js               ← Client HTTP (token JWT)
        └── components/
            ├── LoginPage.jsx    ← Login / inscription
            ├── FeedPanel.jsx    ← Panneau flux
            ├── ArticleList.jsx  ← Liste articles
            ├── ArticleView.jsx  ← Lecteur + TTS intégré
            └── TTSBar.jsx       ← Barre TTS desktop
```

---

## Version web — état actuel

### Authentification (implémentée)
- JWT signé HS256, expiration 30 jours
- Mot de passe hashé avec `bcrypt` (direct, sans passlib)
- Routes : `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Token stocké dans `localStorage` (`rss_token`)
- Déconnexion automatique sur 401

### Multi-utilisateurs
- Table `users` (id, username, password_hash, created_at)
- `feeds.user_id` FK → isolation totale entre comptes
- `UNIQUE(user_id, url)` → deux users peuvent s'abonner au même flux
- Migration automatique : une ancienne DB sans `user_id` est migrée au démarrage,
  les flux orphelins sont assignés à un compte `admin` (mot de passe : variable
  d'env `DEFAULT_ADMIN_PASSWORD`, défaut `changeme123`)

### Déploiement
- **Backend** : Render (free tier, Python 3.14)
  - DB persistante sur disque `/data/rss_reader.db`
  - URL : `https://rssnews-bjc6.onrender.com`
  - ⚠️ Ajouter `SECRET_KEY` en variable d'env Render (sinon clé par défaut non sécurisée)
- **Frontend** : déployé séparément (Netlify ou similaire)
  - Variable d'env build : `VITE_API_URL=https://rssnews-bjc6.onrender.com`

### Fonctionnalités web
- Gestion des flux (ajout, modification, suppression, catégories)
- Détection automatique de l'URL RSS depuis une page web
- Rafraîchissement manuel et par flux
- Liste des articles avec recherche, filtres (tout / non lus / favoris)
- Lecture d'article avec rendu HTML sécurisé (sanitize XSS)
- Zoom texte (A+ / A−)
- Marquer lu/non-lu, favoris
- Import / Export OPML (avec auth token)
- TTS via Web Speech API (barre intégrée dans ArticleView)
- Interface responsive : desktop 3 panneaux, mobile plein écran avec navigation par onglets

---

## Points d'attention pour la suite

- **SECRET_KEY** sur Render : à configurer impérativement en production
- **Refresh automatique** : pas encore implémenté côté web (le desktop a un timer configurable)
- **Sécurité DB** : données en clair sur Render (articles RSS = contenu public, mais les métadonnées de lecture sont visibles)
- **Free tier Render** : le backend "spin-down" après inactivité → première requête lente (~30s)
- La version desktop (PyQt6) est **entièrement indépendante** de la version web et n'a pas été modifiée

---

## Dépendances backend web

```
fastapi, uvicorn, feedparser, requests, beautifulsoup4,
python-multipart, python-jose[cryptography], bcrypt
```

> ⚠️ Ne pas utiliser `passlib` : incompatible avec bcrypt≥4.0 sur Python 3.14
