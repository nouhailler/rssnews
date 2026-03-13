# 📦 RSS Reader — Guide d'installation

## Installation rapide

```bash
sudo dpkg -i rssnews_1.0.0_amd64.deb
```

Au premier lancement, l'application crée automatiquement un environnement
Python isolé dans `~/.local/share/rssnews/venv/` et installe toutes les
dépendances Python. Cette étape prend 1 à 2 minutes.

---

## Prérequis système

```bash
sudo apt install -y python3 python3-venv python3-pyqt6 alsa-utils
```

---

## Lancement

```bash
rssnews
```

Ou depuis le menu Applications → Internet → RSS Reader.

---

## Activation de la lecture à haute voix (TTS offline)

L'application supporte la synthèse vocale offline via **Piper TTS**.

### 1. Installer Piper

```bash
pip install piper-tts pathvalidate --break-system-packages
```

### 2. Télécharger une voix

**Voix française (recommandée) :**

```bash
mkdir -p ~/.local/share/piper
cd ~/.local/share/piper
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
```

D'autres voix disponibles sur : https://huggingface.co/rhasspy/piper-voices/tree/main

### 3. Configurer la voix dans l'application

1. Lancer `rssnews`
2. Cliquer sur ⚙ dans la barre TTS en bas de la fenêtre
3. Naviguer vers `~/.local/share/piper/`
4. Sélectionner le fichier `fr_FR-siwis-medium.onnx`

### 4. Utiliser le TTS

1. Sélectionner un article dans la liste
2. Cliquer sur ▶ dans la barre en bas
3. Contrôles disponibles : ▶ Play — ⏸ Pause — ⏹ Stop — vitesse 0.75x à 2.0x

---

## Désinstallation

```bash
sudo dpkg -r rssnews
```

Les données utilisateur (base de données, cache audio, préférences) restent
dans `~/.local/share/rss-reader/`. Pour les supprimer complètement :

```bash
rm -rf ~/.local/share/rss-reader
rm -rf ~/.local/share/rssnews
```

---

## Fichiers installés

| Chemin | Rôle |
|--------|------|
| `/usr/share/rssnews/` | Code source de l'application |
| `/usr/local/bin/rssnews` | Script de lancement |
| `/usr/share/applications/rssnews.desktop` | Entrée menu applications |
| `~/.local/share/rssnews/venv/` | Environnement Python (créé au 1er lancement) |
| `~/.local/share/rss-reader/` | Données utilisateur (BDD, cache, préférences) |
