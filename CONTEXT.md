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
├── database.py          ← DB desktop SQLite (séparée de la web)
├── rss_fetcher.py       ← Fetcher desktop
├── ui/                  ← Interface Qt (main_window, feed_panel, article_list,
│                           article_view, tts_bar, dialogs)
├── tts/                 ← Piper TTS offline
├── install.sh           ← Installeur Linux
│
├── backend/             ← API FastAPI (version web)
│   ├── main.py          ← Routes REST + auth
│   ├── database.py      ← PostgreSQL multi-utilisateurs (psycopg2)
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
- `get_current_user` vérifie l'existence de l'utilisateur en DB (évite le FOREIGN KEY
  constraint failed si la DB est réinitialisée avec un vieux JWT en localStorage)

### Multi-utilisateurs

- Table `users` (id, username, password_hash, created_at)
- `feeds.user_id` FK → isolation totale entre comptes
- `UNIQUE(user_id, url)` → deux users peuvent s'abonner au même flux
- Migration automatique : si la table `feeds` n'a pas de colonne `user_id`,
  elle est ajoutée au démarrage (`_migrate_if_needed`)

### Base de données web

- **PostgreSQL** hébergé sur **Neon** (serverless, free tier 0,5 GB)
- Driver : `psycopg2-binary` (wheel précompilé, pas de compilation Rust)
- Wrapper `_Conn` dans `database.py` expose `conn.execute()` comme sqlite3
- `RealDictCursor` → résultats sous forme de `dict`
- Paramètres SQL : `%s` (PostgreSQL, pas `?`)
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- `AUTOINCREMENT` → `SERIAL` + `RETURNING id` pour récupérer le dernier id

### Déploiement

- **Backend** : Render (free tier, Python 3.14)
  - URL : `https://rssnews-bjc6.onrender.com`
  - Variables d'env **obligatoires** :
    - `SECRET_KEY` — clé de signature JWT
    - `DATABASE_URL` — connection string Neon (`postgresql://...`)
  - Le service "spin-down" après inactivité → première requête ~30 s
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

- **DATABASE_URL** sur Render : à configurer avec la connection string Neon
- **SECRET_KEY** sur Render : à configurer impérativement en production
- **Refresh automatique** : pas encore implémenté côté web (le desktop a un timer configurable)
- **CORS** : `allow_origins=["*"]` — à restreindre en production si nécessaire
- **Free tier Render** : le backend "spin-down" après inactivité → première requête lente (~30 s)
- La version desktop (PyQt6) est **entièrement indépendante** de la version web et n'a pas été modifiée

---

## Dépendances backend web

```
fastapi, uvicorn, feedparser, requests, beautifulsoup4,
python-multipart, python-jose[cryptography], bcrypt, psycopg2-binary
```

> Ne pas utiliser `passlib` : incompatible avec bcrypt >= 4.0 sur Python 3.14  
> Ne pas utiliser `libsql-experimental` : nécessite Rust (filesystem read-only sur Render)

---

## Fichiers de documentation

| Fichier | Contenu |
|---------|---------|
| `README.md` | Présentation, installation, fonctionnalités (les deux versions) |
| `CONTEXT.md` | Ce fichier — état du projet pour reprendre en session future |
| `CLAUDE.md` | Guide Claude Code : architecture, conventions, règles critiques |
| `INSTALL.md` | Guide d'installation du paquet `.deb` desktop + TTS |
