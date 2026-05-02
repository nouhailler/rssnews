# CLAUDE.md — Guide de travail pour Claude Code

Ce fichier documente l'architecture, les conventions et les points d'attention
pour travailler efficacement sur ce projet avec Claude Code.

---

## Architecture : deux applications coexistantes

Le dépôt contient **deux applications indépendantes** qui partagent la même
logique métier (parsing RSS, OPML) mais n'ont aucune dépendance entre elles.

| App | Entrée | Stack | Usage |
|-----|--------|-------|-------|
| Desktop | `main.py` (racine) | Python 3.10+, PyQt6, SQLite, Piper TTS | Linux uniquement |
| Web | `backend/main.py` + `frontend/` | FastAPI, React (Vite), SQLite, Web Speech API | Navigateur, mobile, déployé sur Render |

Ne pas mélanger les deux : modifier `database.py` racine n'affecte pas
`backend/database.py`, et vice-versa.

---

## Structure des dossiers

```
rssnews/
├── main.py              ← App desktop (PyQt6)
├── database.py          ← DB desktop (SQLite, séparée)
├── rss_fetcher.py       ← Fetcher desktop
├── ui/                  ← Widgets Qt (main_window, feed_panel, article_list, article_view, tts_bar, dialogs)
├── tts/                 ← Piper TTS offline (tts_manager, audio_player, text_cleaner)
├── install.sh           ← Installeur Linux + .deb
│
├── backend/             ← API REST FastAPI (version web)
│   ├── main.py          ← Toutes les routes (auth, feeds, articles, OPML)
│   ├── database.py      ← SQLite multi-utilisateurs
│   ├── auth.py          ← JWT HS256 (python-jose) + bcrypt direct
│   ├── rss_fetcher.py   ← Même logique que desktop
│   ├── requirements.txt
│   └── render.yaml      ← Config déploiement Render (free tier)
│
└── frontend/            ← SPA React (Vite)
    └── src/
        ├── main.jsx
        ├── App.jsx              ← Auth state, layout 3 panneaux / mobile
        ├── App.css
        ├── api.js               ← Toutes les fonctions fetch (token JWT Bearer)
        └── components/
            ├── LoginPage.jsx    ← Login + inscription
            ├── FeedPanel.jsx    ← Arborescence des flux par catégorie
            ├── ArticleList.jsx  ← Liste filtrée (tout / non-lus / favoris / recherche)
            ├── ArticleView.jsx  ← Lecteur HTML + TTS Web Speech API intégré
            └── TTSBar.jsx       ← Barre TTS (utilisée par la version desktop Qt)
```

---

## Authentification web

- JWT signé HS256, durée 30 jours, stocké dans `localStorage` (`rss_token`)
- Mot de passe hashé avec `bcrypt` **direct** (import `bcrypt`, pas `passlib`)
- `SECRET_KEY` lue depuis `os.environ` — à configurer sur Render en production
- Routes : `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Toutes les routes métier utilisent `Depends(auth.get_current_user)`
- Déconnexion automatique côté React sur réponse HTTP 401

### Règle critique : ne jamais utiliser passlib

`passlib` est incompatible avec `bcrypt >= 4.0` sur Python 3.14 (Render).
Toujours utiliser `bcrypt` directement :

```python
import bcrypt
bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
bcrypt.checkpw(plain.encode(), hashed.encode())
```

---

## Base de données web (`backend/database.py`)

- Driver : `libsql-experimental` (libSQL/Turso, compatible SQLite)
- En production : connexion distante via `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`
- En dev local : fichier SQLite local (fallback automatique si vars Turso absentes)
- `row_factory` personnalisé (`_dict_factory`) → les lignes sont des `dict` (pas `sqlite3.Row`)

### Schéma

```sql
users   (id, username, password_hash, created_at)
feeds   (id, user_id FK, name, url, category, active, created_at)
articles(id, feed_id FK, title, link, published_date, content, summary,
         read_status, favorite, created_at)
```

- `UNIQUE(user_id, url)` sur feeds : deux users peuvent s'abonner au même flux
- Migration automatique au démarrage : feeds sans `user_id` → compte `admin`
  (mot de passe : var env `DEFAULT_ADMIN_PASSWORD`, défaut `changeme123`)

---

## API REST — résumé des routes

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/auth/register` | Créer un compte |
| POST | `/auth/login` | Se connecter (OAuth2 form) |
| GET | `/auth/me` | Profil utilisateur courant |
| GET | `/feeds` | Liste des flux + compteurs non-lus |
| POST | `/feeds` | Ajouter un flux |
| POST | `/feeds/discover` | Détecter l'URL RSS depuis une page web |
| GET/PUT/DELETE | `/feeds/{id}` | CRUD flux |
| PATCH | `/feeds/{id}/active` | Activer / désactiver |
| POST | `/feeds/{id}/refresh` | Rafraîchir un flux |
| POST | `/refresh` | Rafraîchir tous les flux actifs |
| GET | `/articles` | Liste (filtres: feed_id, smart, search) |
| GET/PATCH | `/articles/{id}` | Lire / modifier (lu, favori) |
| POST | `/articles/mark-all-read` | Marquer tout lu |
| POST | `/opml/import` | Importer un fichier OPML |
| GET | `/opml/export` | Exporter les flux en OPML |

---

## Déploiement

### Backend — Render (free tier)

- URL : `https://rssnews-bjc6.onrender.com`
- DB hébergée sur **Turso** (libSQL distant) — pas de disque local nécessaire
- Le service "spin-down" après inactivité → première requête ~30 s
- Variables d'env **obligatoires** en production :
  - `SECRET_KEY` — clé JWT
  - `TURSO_DATABASE_URL` — URL libsql://… fournie par Turso
  - `TURSO_AUTH_TOKEN` — token d'authentification Turso
- Fallback local (dev) : SQLite dans `~/.local/share/rss-reader/rss_reader.db`

### Frontend — Netlify (ou similaire)

- Variable d'env build : `VITE_API_URL=https://rssnews-bjc6.onrender.com`
- `api.js` lit `import.meta.env.VITE_API_URL`

---

## Conventions de travail

- Commits fréquents, push systématique après chaque feature/fix
- Messages de commit en français
- Pas de mocks pour les tests DB — utiliser une vraie SQLite en mémoire
- Pas de `passlib` (voir règle critique ci-dessus)
- Pas de `async` dans `database.py` (SQLite synchrone, FastAPI gère les threads)

---

## Points d'attention

- Le refresh automatique n'est **pas implémenté** côté web (contrairement au desktop)
- Le CORS est actuellement `allow_origins=["*"]` — à restreindre en production
- Les données RSS sont publiques mais les métadonnées de lecture (lu/favori) sont
  personnelles → la DB Render est en clair sur le disque
