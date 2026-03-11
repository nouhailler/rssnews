# 📰 RSS Reader — Lecteur de flux RSS pour Linux

> Application de bureau multiplateforme avec interface graphique Qt6, conçue pour Linux.
> Créée avec [Claude Code](https://claude.ai/code).

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white) ![PyQt6](https://img.shields.io/badge/PyQt6-6.x-41CD52?style=flat-square&logo=qt&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white) ![License](https://img.shields.io/badge/Licence-MIT-yellow?style=flat-square)

---

## 📁 Structure du projet

```
rss_reader/
├── main.py              # Point d'entrée
├── database.py          # Toutes les opérations SQLite
├── rss_fetcher.py       # Récupération RSS (module principal)
├── requirements.txt     # PyQt6, feedparser, requests
├── install.sh           # Script d'installation automatique
└── ui/
    ├── __init__.py
    ├── main_window.py   # Fenêtre 3 panneaux + menus
    ├── feed_panel.py    # Panneau gauche (arborescence des flux)
    ├── article_list.py  # Panneau central (liste des articles)
    ├── article_view.py  # Panneau droit (lecteur d'articles)
    └── dialogs.py       # Boîtes de dialogue
```

---

## 🚀 Installation

```bash
git clone https://github.com/nouhailler/rssnews.git
cd rssnews
./install.sh
```

Le script installe l'application dans un `venv` isolé et crée un lanceur dans `~/.local/bin/rss-reader`.

---

## ✨ Fonctionnalités

### 📡 Gestion des flux

- Ajouter, modifier et supprimer des flux RSS
- Organisation par **catégories éditables**
- Détection automatique du titre RSS lors de l'ajout
- Activation / désactivation par clic droit

### 🔄 Récupération RSS

- Messages d'erreur précis pour chaque cas :
  - DNS introuvable, timeout, erreur SSL
  - HTTP 403 / 404 / 500
  - XML malformé, URL non-RSS, réponse vide, trop de redirections
- Rafraîchissement dans un **thread séparé** (non-bloquant)
- Mise à jour automatique configurable (5 à 240 min)
- Dialogue de progression avec log détaillé

### 📖 Lecture

- Interface **3 panneaux** redimensionnables
- Rendu HTML sécurisé (sans JavaScript, ressources externes bloquées)
- Zoom du texte (A+ / A−)
- Marquer lu / non-lu, favoris, marquage global
- Recherche avec debounce 300 ms
- Ouverture dans le navigateur (`xdg-open`)

### 💾 Import / Export

- Support **OPML** (import et export)
- Persistance : géométrie de fenêtre, taille des panneaux, préférences

---

## 🛠️ Dépendances

| Paquet       | Rôle                           |
|--------------|--------------------------------|
| `PyQt6`      | Interface graphique            |
| `feedparser` | Parsing des flux RSS/Atom      |
| `requests`   | Requêtes HTTP                  |
| `SQLite3`    | Base de données locale (stdlib)|

---

## 📄 Licence

MIT — libre d'utilisation, modification et distribution.
