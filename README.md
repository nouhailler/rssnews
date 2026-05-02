# RSS Reader

> Lecteur de flux RSS en deux versions : application de bureau Linux (PyQt6)
> et application web full-stack (FastAPI + React).
> Créé avec [Claude Code](https://claude.ai/code).

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-41CD52?style=flat-square&logo=qt&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/Licence-MIT-yellow?style=flat-square)

---

## Deux versions indépendantes

| Version | Stack | Usage |
|---------|-------|-------|
| **Desktop** (`main.py`) | Python + PyQt6 + Piper TTS | Linux uniquement |
| **Web** (`backend/` + `frontend/`) | FastAPI + React + Web Speech API | Navigateur, mobile |

---

## Version Web

### Démarrage rapide

```bash
# Backend
cd backend
pip install -r requirements.txt
# Définir DATABASE_URL (connection string PostgreSQL/Neon)
export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
uvicorn main:app --reload

# Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

Ouvrir `http://localhost:5173` — créer un compte et commencer à ajouter des flux.

### Fonctionnalités

- **Authentification multi-utilisateurs** : inscription, connexion (JWT 30 jours),
  isolation totale des données entre comptes
- **Gestion des flux** : ajout, modification, suppression, catégories,
  activation / désactivation, détection automatique de l'URL RSS depuis une page web
- **Lecture** : interface 3 panneaux (desktop) ou navigation par onglets (mobile),
  rendu HTML sécurisé, zoom texte, marquer lu/non-lu, favoris
- **Filtres** : tout / non-lus / favoris, recherche plein texte
- **TTS** : lecture à haute voix via Web Speech API (barre intégrée dans le lecteur)
- **Import / Export OPML**
- **Rafraîchissement** : manuel (flux par flux ou tous les flux actifs)

### Déploiement

- **Backend** sur [Render](https://render.com) (free tier, `render.yaml` inclus)
  - URL de production : `https://rssnews-bjc6.onrender.com`
  - Variables d'env à configurer sur Render :
    - `SECRET_KEY` — clé de signature JWT (obligatoire)
    - `DATABASE_URL` — connection string [Neon](https://neon.tech) PostgreSQL
- **Frontend** sur Netlify ou similaire
  - Variable de build : `VITE_API_URL=https://rssnews-bjc6.onrender.com`

### Structure

```
backend/
├── main.py          ← Routes REST (auth, feeds, articles, OPML)
├── database.py      ← PostgreSQL multi-utilisateurs (psycopg2)
├── auth.py          ← JWT HS256 + bcrypt
├── rss_fetcher.py   ← Parsing RSS / OPML
├── requirements.txt
└── render.yaml      ← Config Render

frontend/src/
├── App.jsx          ← Auth state, layout
├── api.js           ← Client HTTP (Bearer token)
└── components/
    ├── LoginPage.jsx
    ├── FeedPanel.jsx
    ├── ArticleList.jsx
    └── ArticleView.jsx  ← Lecteur + TTS
```

---

## Version Desktop (Linux)

### Installation

```bash
git clone https://github.com/nouhailler/rssnews.git
cd rssnews
./install.sh
```

Le script crée un `venv` isolé et un lanceur dans `~/.local/bin/rss-reader`.

```bash
sudo apt install -y alsa-utils
pip install piper-tts pathvalidate --break-system-packages
```

### Fonctionnalités

- Interface **3 panneaux** redimensionnables (flux / articles / lecteur)
- Rendu HTML sécurisé (sans JavaScript, ressources externes bloquées)
- Zoom texte, marquer lu/non-lu, favoris, recherche avec debounce
- Rafraîchissement automatique configurable (5 à 240 min)
- Import / Export OPML
- **TTS offline** via [Piper TTS](https://github.com/rhasspy/piper) : lecture à haute voix, pause, stop, vitesse 0.75x–2.0x, cache audio MD5

#### Installer la voix française (TTS)

```bash
mkdir -p ~/.local/share/piper && cd ~/.local/share/piper
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
```

Dans l'application : cliquer sur ⚙ dans la barre TTS → sélectionner le fichier `.onnx`.

### Structure

```
main.py          ← Point d'entrée
database.py      ← SQLite local
rss_fetcher.py   ← Parsing RSS / OPML
ui/              ← Widgets Qt
tts/             ← Piper TTS (manager, player, cleaner)
install.sh       ← Installeur Linux
```

---

## Dépendances

### Backend web

| Paquet | Rôle |
|--------|------|
| `fastapi` + `uvicorn` | Serveur API REST |
| `feedparser` | Parsing RSS/Atom |
| `requests` + `beautifulsoup4` | Fetch + nettoyage HTML |
| `python-jose[cryptography]` | JWT |
| `bcrypt` | Hash des mots de passe |
| `python-multipart` | Upload OPML |
| `psycopg2-binary` | Client PostgreSQL |

### Desktop

| Paquet | Rôle |
|--------|------|
| `PyQt6` | Interface graphique |
| `feedparser` | Parsing RSS/Atom |
| `requests` + `beautifulsoup4` | Fetch + TTS |
| `piper-tts` | Synthèse vocale offline |
| `pathvalidate` | Validation des noms de fichiers |

---

## Licence

MIT — libre d'utilisation, modification et distribution.
