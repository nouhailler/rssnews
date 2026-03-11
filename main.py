#!/usr/bin/env python3
"""
RSS Reader — Lecteur de fils RSS pour Linux
Point d'entrée de l'application.
"""

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration du logging (avant tout import applicatif)
# ---------------------------------------------------------------------------

LOG_DIR = Path.home() / ".local" / "share" / "rss-reader"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "rss_reader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("rss_reader")

# ---------------------------------------------------------------------------
# Vérification des dépendances au démarrage
# ---------------------------------------------------------------------------

def _check_dependencies():
    missing = []
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        missing.append("PyQt6")
    try:
        import feedparser  # noqa: F401
    except ImportError:
        missing.append("feedparser")
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append("requests")

    if missing:
        print(
            f"ERREUR : dépendances manquantes : {', '.join(missing)}\n"
            "Installez-les avec :\n"
            f"  pip install {' '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------

def main():
    _check_dependencies()

    # Import après vérification des dépendances
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    import database as db
    from ui.main_window import MainWindow

    # Initialisation de la base de données
    try:
        db.init_db()
    except Exception as exc:
        logger.critical("Impossible d'initialiser la base de données : %s", exc)
        print(f"ERREUR CRITIQUE : impossible d'initialiser la base de données :\n{exc}", file=sys.stderr)
        sys.exit(1)

    # Création de l'application Qt
    app = QApplication(sys.argv)
    app.setApplicationName("RSS Reader")
    app.setApplicationVersion("0.1")
    app.setOrganizationName("rss-reader")

    # Style global
    app.setStyle("Fusion")

    # Fenêtre principale
    window = MainWindow()
    window.show()

    logger.info("RSS Reader démarré")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
