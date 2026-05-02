# CONTEXT.md — État du projet RSS Reader

Fichier de contexte pour reprendre le travail en session future.
Dernière mise à jour : 2 mai 2026.

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
├── ui/                  ← Interface Qt (main_window, feed_panel, article_list,
│                           article_view, tts_bar, dialogs)
├── tts/                 ← Piper TTS offline
├── install.sh           ← Installeur Linux
│
├── backend/             ← API FastAPI (version web)
│   ├── main.py          ← Routes REST + auth
│   ├── database.py      ← SQLite multi-utilisateurs
│   ├── auth.py          ← JWT (python-jose) + bcrypt direct
│   ├── rss_fetcher.py   ← Même logique que desktop
│   ├── requirements.txt
│   └── render.yaml      ← Config déploiement Render (free tier)
│
└── frontend/            ← Interface React (Vite)
    └── src/
        ├── App.jsx              ← Gestion auth + layout
        ├── api.js               ← Client HTTP (token JWT Bearer)
        └── components/
            ├── LoginPage.jsx    ← Login / inscription
            ├── FeedPanel.jsx    ← Panneau flux par catégorie
            ├── ArticleList.jsx  ← Liste articles (filtres + recherche)
            ├── ArticleView.jsx  ← Lecteur HTML + TTS intégré
            └── TTSBar.jsx       ← Barre TTS desktop Qt
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
  - Variable d'env **obligatoire** : `SECRET_KEY` (sinon clé par défaut non sécurisée)
- **Frontend** : Netlify ou similaire
  - Variable d'env build : `VITE_API_URL=https://rssnews-bjc6.onrender.com`

### Fonctionnalités web (toutes implémentées)

- Gestion des flux (ajout, modification, suppression, catégories)
- Détection automatique de l'URL RSS depuis une page web
- Rafraîchissement manuel par flux et global (tous les flux actifs)
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
- **CORS** : `allow_origins=["*"]` — à restreindre en production si nécessaire
- **Free tier Render** : le backend "spin-down" après inactivité → première requête lente (~30s)
- La version desktop (PyQt6) est **entièrement indépendante** de la version web et n'a pas été modifiée

---

## Dépendances backend web

```
fastapi, uvicorn, feedparser, requests, beautifulsoup4,
python-multipart, python-jose[cryptography], bcrypt
```

> Ne pas utiliser `passlib` : incompatible avec bcrypt >= 4.0 sur Python 3.14

---

## Fichiers de documentation

| Fichier | Contenu |
|---------|---------|
| `README.md` | Présentation, installation, fonctionnalités (les deux versions) |
| `CONTEXT.md` | Ce fichier — état du projet pour reprendre en session future |
| `CLAUDE.md` | Guide Claude Code : architecture, conventions, règles critiques |
| `INSTALL.md` | Guide d'installation du paquet `.deb` desktop + TTS |
