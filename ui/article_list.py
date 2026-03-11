"""
Panneau central : liste des articles.

Affiche les articles triés du plus récent au plus ancien.
Chaque article montre : titre, source (flux), date.
Les articles non lus apparaissent en gras.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import database as db

ROLE_ARTICLE_ID = Qt.ItemDataRole.UserRole


class ArticleListPanel(QWidget):
    """
    Panneau liste des articles.

    Signaux :
      article_selected(article_id)  — un article a été cliqué
    """

    article_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_feed_id: int | None = None
        self._current_smart: str | None = "all"
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)   # debounce 300 ms
        self._search_timer.timeout.connect(self._apply_search)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barre de recherche
        search_bar = QHBoxLayout()
        search_bar.setContentsMargins(6, 4, 6, 4)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Rechercher dans les articles…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_bar.addWidget(self._search_edit)

        self._mark_all_btn = QPushButton("Tout lire")
        self._mark_all_btn.setFixedWidth(70)
        self._mark_all_btn.setToolTip("Marquer tous les articles visibles comme lus")
        self._mark_all_btn.clicked.connect(self._on_mark_all_read)
        search_bar.addWidget(self._mark_all_btn)

        layout.addLayout(search_bar)

        # Compteur
        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 2px 8px;"
        )
        layout.addWidget(self._count_label)

        # Liste
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.currentItemChanged.connect(self._on_item_changed)
        self._list.setStyleSheet("""
            QListWidget {
                border: none;
                background: #ffffff;
                font-size: 13px;
            }
            QListWidget::item {
                border-bottom: 1px solid #ecf0f1;
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background: #f0f7ff;
            }
        """)
        layout.addWidget(self._list)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(260)

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def load_feed(self, feed_id: int):
        self._current_feed_id = feed_id
        self._current_smart   = None
        self._search_edit.clear()
        self._refresh_list()

    def load_smart(self, smart: str):
        self._current_smart   = smart
        self._current_feed_id = None
        self._search_edit.clear()
        self._refresh_list()

    def refresh(self):
        """Recharge la liste courante (après une mise à jour des flux)."""
        self._refresh_list()

    def _refresh_list(self):
        search  = self._search_edit.text().strip()
        only_unread    = self._current_smart == "unread"
        only_favorites = self._current_smart == "favorites"

        articles = db.get_articles(
            feed_id        = self._current_feed_id,
            only_unread    = only_unread,
            only_favorites = only_favorites,
            search         = search,
        )

        # Sauvegarde l'article actuellement sélectionné
        current = self._list.currentItem()
        saved_id = current.data(ROLE_ARTICLE_ID) if current else None

        self._list.clear()
        restored = False

        for art in articles:
            item = QListWidgetItem()
            item.setData(ROLE_ARTICLE_ID, art["id"])

            # Construction du texte de l'item (multiligne via setData + delegate ou
            # via le flag Qt.ItemDataRole.DisplayRole multi-ligne)
            title   = art.get("title") or "(sans titre)"
            source  = art.get("feed_name", "")
            date_str = _format_date(art.get("published_date") or art.get("fetch_date", ""))

            # On compose une chaîne multiligne
            text = f"{title}\n{source}  —  {date_str}"
            item.setText(text)

            # Article non lu → gras
            if not art.get("read_status"):
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            # Favori → couleur
            if art.get("favorite"):
                item.setForeground(QColor("#e67e22"))

            self._list.addItem(item)

            if art["id"] == saved_id:
                self._list.setCurrentItem(item)
                restored = True

        unread_count = sum(1 for a in articles if not a.get("read_status"))
        total = len(articles)
        self._count_label.setText(
            f"{total} article{'s' if total > 1 else ''}  •  {unread_count} non lu{'s' if unread_count > 1 else ''}"
        )

        if not restored and self._list.count() > 0:
            # Ne pas sélectionner automatiquement pour ne pas déclencher le marquage lu
            pass

    # ------------------------------------------------------------------
    # Recherche avec debounce
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        self._search_timer.start()

    def _apply_search(self):
        self._refresh_list()

    # ------------------------------------------------------------------
    # Marquer tout comme lu
    # ------------------------------------------------------------------

    def _on_mark_all_read(self):
        db.mark_all_read(self._current_feed_id)
        self._refresh_list()
        # On émet une sélection "rien" pour forcer le rechargement du panneau feeds
        # (sera géré par main_window)

    # ------------------------------------------------------------------
    # Signaux de sélection
    # ------------------------------------------------------------------

    def _on_item_changed(self, current: QListWidgetItem, _previous):
        if not current:
            return
        article_id = current.data(ROLE_ARTICLE_ID)
        if article_id is not None:
            self.article_selected.emit(article_id)

    # ------------------------------------------------------------------
    # Menu contextuel
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        article_id = item.data(ROLE_ARTICLE_ID)
        if article_id is None:
            return

        art = db.get_article(article_id)
        if not art:
            return

        menu = QMenu(self)
        is_read     = bool(art.get("read_status"))
        is_favorite = bool(art.get("favorite"))

        if is_read:
            a_read = menu.addAction("Marquer comme non lu")
            a_read.triggered.connect(lambda: self._toggle_read(article_id, False, item))
        else:
            a_read = menu.addAction("Marquer comme lu")
            a_read.triggered.connect(lambda: self._toggle_read(article_id, True, item))

        if is_favorite:
            a_fav = menu.addAction("Retirer des favoris")
            a_fav.triggered.connect(lambda: self._toggle_favorite(article_id, False, item))
        else:
            a_fav = menu.addAction("Ajouter aux favoris ⭐")
            a_fav.triggered.connect(lambda: self._toggle_favorite(article_id, True, item))

        if art.get("link"):
            menu.addSeparator()
            a_open = menu.addAction("Ouvrir dans le navigateur")
            a_open.triggered.connect(lambda: _open_url(art["link"]))

        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _toggle_read(self, article_id: int, read: bool, item: QListWidgetItem):
        db.set_article_read(article_id, read)
        font = item.font()
        font.setBold(not read)
        item.setFont(font)

    def _toggle_favorite(self, article_id: int, fav: bool, item: QListWidgetItem):
        db.set_article_favorite(article_id, fav)
        item.setForeground(QColor("#e67e22") if fav else QColor())

    # ------------------------------------------------------------------
    # Helpers publics
    # ------------------------------------------------------------------

    def get_selected_article_id(self) -> int | None:
        item = self._list.currentItem()
        return item.data(ROLE_ARTICLE_ID) if item else None

    def mark_current_as_read(self):
        """Marque l'article courant comme lu et met à jour l'affichage."""
        item = self._list.currentItem()
        if not item:
            return
        article_id = item.data(ROLE_ARTICLE_ID)
        if article_id is None:
            return
        db.set_article_read(article_id, True)
        font = item.font()
        font.setBold(False)
        item.setFont(font)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_date(date_str: str) -> str:
    """Formate une date ISO en chaîne lisible."""
    if not date_str:
        return ""
    try:
        # Tronque aux 19 premiers caractères pour gérer les variantes ISO
        dt = datetime.fromisoformat(date_str[:19])
        now = datetime.now()
        delta = now - dt
        if delta.days == 0:
            return f"Aujourd'hui {dt.strftime('%H:%M')}"
        elif delta.days == 1:
            return f"Hier {dt.strftime('%H:%M')}"
        elif delta.days < 7:
            jours = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
            return f"{jours[dt.weekday()]} {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%d/%m/%Y")
    except Exception:
        return date_str[:10] if len(date_str) >= 10 else date_str


def _open_url(url: str):
    """Ouvre l'URL dans le navigateur par défaut."""
    import subprocess
    try:
        subprocess.Popen(["xdg-open", url])
    except Exception:
        pass
