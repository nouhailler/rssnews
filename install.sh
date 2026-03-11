#!/usr/bin/env bash
# ============================================================
# install.sh — Installation du lecteur RSS
# ============================================================
# Usage : ./install.sh
#
# Ce script :
#   1. Vérifie que Python 3.10+ est disponible
#   2. Crée un environnement virtuel dans .venv/
#   3. Installe les dépendances (PyQt6, feedparser, requests)
#   4. Crée un lanceur desktop (rss-reader.desktop)
#   5. Crée un script wrapper rss-reader dans ~/bin/
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warning() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERREUR]${NC} $*" >&2; }

# ============================================================
# 1. Vérification de Python
# ============================================================

info "Vérification de Python 3..."

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(sys.version_info[:2])")
        # Vérifie que la version est >= (3, 10)
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.10 ou supérieur est requis."
    error "Installez-le avec :"
    error "  Ubuntu/Debian : sudo apt install python3 python3-venv"
    error "  Fedora        : sudo dnf install python3"
    error "  Arch Linux    : sudo pacman -S python"
    exit 1
fi

success "Python trouvé : $($PYTHON --version)"

# ============================================================
# 2. Vérification de pip / venv
# ============================================================

info "Vérification du module venv..."
if ! "$PYTHON" -m venv --help &>/dev/null; then
    error "Le module 'venv' est manquant."
    error "Installez-le avec :"
    error "  Ubuntu/Debian : sudo apt install python3-venv"
    exit 1
fi

# ============================================================
# 3. Création de l'environnement virtuel
# ============================================================

if [ ! -d "$VENV_DIR" ]; then
    info "Création de l'environnement virtuel dans .venv/..."
    "$PYTHON" -m venv "$VENV_DIR"
    success "Environnement virtuel créé."
else
    info "Environnement virtuel existant trouvé."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ============================================================
# 4. Installation des dépendances
# ============================================================

info "Mise à jour de pip..."
"$VENV_PIP" install --quiet --upgrade pip

info "Installation des dépendances (PyQt6, feedparser, requests)..."
if "$VENV_PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"; then
    success "Dépendances installées avec succès."
else
    error "L'installation des dépendances a échoué."
    error ""
    error "Solutions possibles :"
    error "  PyQt6 nécessite parfois des bibliothèques système :"
    error "    Ubuntu/Debian : sudo apt install python3-pyqt6 libgl1"
    error "    Fedora        : sudo dnf install python3-pyqt6"
    error "    Arch Linux    : sudo pacman -S python-pyqt6"
    error ""
    error "  Alternative : installer PyQt6 via votre gestionnaire de paquets"
    error "  puis relancer ce script."
    exit 1
fi

# Vérification que PyQt6 est fonctionnel
info "Vérification de PyQt6..."
if ! "$VENV_PYTHON" -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null; then
    warning "PyQt6 est installé mais semble non fonctionnel."
    warning "Si vous êtes en environnement sans affichage (SSH), c'est normal."
    warning "L'application nécessite un serveur X11 ou Wayland pour s'exécuter."
fi

# ============================================================
# 5. Création du script wrapper
# ============================================================

mkdir -p "$BIN_DIR"

WRAPPER="$BIN_DIR/rss-reader"
cat > "$WRAPPER" << WRAPPER_EOF
#!/usr/bin/env bash
# Lanceur RSS Reader
exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py" "\$@"
WRAPPER_EOF

chmod +x "$WRAPPER"
success "Script lanceur créé : $WRAPPER"

# ============================================================
# 6. Fichier .desktop (lanceur graphique)
# ============================================================

mkdir -p "$DESKTOP_DIR"

DESKTOP_FILE="$DESKTOP_DIR/rss-reader.desktop"
cat > "$DESKTOP_FILE" << DESKTOP_EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RSS Reader
Comment=Lecteur de flux RSS/Atom pour Linux
Exec=$VENV_PYTHON $SCRIPT_DIR/main.py
Icon=application-rss+xml
Terminal=false
Categories=Network;News;
Keywords=rss;atom;news;feed;lecteur;
StartupNotify=true
DESKTOP_EOF

chmod +x "$DESKTOP_FILE"
success "Fichier .desktop créé : $DESKTOP_FILE"

# Mise à jour de la base de données des applications
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# ============================================================
# Résumé
# ============================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation terminée avec succès !  ${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Pour lancer l'application :"
echo ""
echo "  Option 1 — Depuis le terminal :"
echo "    rss-reader"
echo "    (si $BIN_DIR est dans votre PATH)"
echo ""
echo "  Option 2 — Directement :"
echo "    $VENV_PYTHON $SCRIPT_DIR/main.py"
echo ""
echo "  Option 3 — Menu applications :"
echo "    Cherchez « RSS Reader » dans votre menu"
echo ""

# Avertissement PATH si nécessaire
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warning "$BIN_DIR n'est pas dans votre PATH."
    warning "Ajoutez cette ligne à votre ~/.bashrc ou ~/.zshrc :"
    warning "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
