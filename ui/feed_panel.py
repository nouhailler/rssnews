"""
Panneau gauche : arborescence des flux RSS.

Affiche :
  - Tous les articles
  - Non lus
  - Favoris
  - Flux organisés par catégorie
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import database as db


# Rôles personnalisés pour stocker les données dans les items
ROLE_TYPE    = Qt.ItemDataRole.UserRole        # "smart" | "category" | "feed"
ROLE_FEED_ID = Qt.ItemDataRole.UserRole + 1   # int (feed_id) ou None
ROLE_SMART   = Qt.ItemDataRole.UserRole + 2   # "all" | "unread" | "favorites"

_SMART_ICONS = {
    "all":       "📰",
    "unread":    "🔵",
    "favorites": "⭐",
}

_CAT_ICON = "📁"
_FEED_ICON = "📄"
_ERROR_ICON = "⚠"


class FeedPanel(QFrame):
    """
    Widget arborescence des flux.

    Signaux émis :
      feed_selected(feed_id)   — un flux spécifique a été sélectionné
      smart_selected(smart)    — "all", "unread" ou "favorites"
    """

    feed_selected  = pyqtSignal(int)
    smart_selected = pyqtSignal(str)

    # Signaux pour les actions contextuelles
    add_feed_requested     = pyqtSignal()
    edit_feed_requested    = pyqtSignal(int)
    delete_feed_requested  = pyqtSignal(int)
    refresh_feed_requested = pyqtSignal(int)
    mark_all_read_feed     = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._unread_counts: dict[int, int] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  Flux RSS")
        header.setFixedHeight(32)
        header.setStyleSheet(
            "background:#2c3e50; color:white; font-weight:bold; font-size:13px;"
        )
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        self._tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                background: #f8f9fa;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QTreeWidget::item:hover:!selected {
                background: #e8f4fd;
            }
        """)

        layout.addWidget(self._tree)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(180)

    # ------------------------------------------------------------------
    # Chargement / Rafraîchissement de l'arbre
    # ------------------------------------------------------------------

    def load(self, feeds: list[dict] | None = None):
        """
        Reconstruit l'arbre à partir de la base de données.
        Préserve l'item sélectionné si possible.
        """
        # Sauvegarde de la sélection actuelle
        current_item = self._tree.currentItem()
        saved_type    = current_item.data(0, ROLE_TYPE)    if current_item else None
        saved_smart   = current_item.data(0, ROLE_SMART)   if current_item else None
        saved_feed_id = current_item.data(0, ROLE_FEED_ID) if current_item else None

        self._unread_counts = db.get_unread_counts_by_feed()
        total_unread = sum(self._unread_counts.values())

        self._tree.blockSignals(True)
        self._tree.clear()

        if feeds is None:
            feeds = db.get_all_feeds()
        # --- Entrées intelligentes ------------------------------------
        smart_items = self._make_smart_items(total_unread)
        for item in smart_items:
            self._tree.addTopLevelItem(item)

        # Séparateur visuel
        sep = QTreeWidgetItem([""])
        sep.setFlags(Qt.ItemFlag.NoItemFlags)
        sep.setDisabled(True)
        self._tree.addTopLevelItem(sep)

        # --- Catégories et flux ---------------------------------------
        by_cat: dict[str, list[dict]] = {}
        for f in feeds:
            by_cat.setdefault(f["category"], []).append(f)

        cat_items: dict[str, QTreeWidgetItem] = {}
        for cat in sorted(by_cat.keys()):
            cat_item = self._make_category_item(cat, by_cat[cat])
            self._tree.addTopLevelItem(cat_item)
            cat_items[cat] = cat_item

            for feed in sorted(by_cat[cat], key=lambda x: x["name"].lower()):
                feed_item = self._make_feed_item(feed)
                cat_item.addChild(feed_item)

            cat_item.setExpanded(True)

        # --- Restauration de la sélection ----------------------------
        restored = False
        if saved_type == "smart" and saved_smart:
            restored = self._select_smart(saved_smart)
        elif saved_type == "feed" and saved_feed_id:
            restored = self._select_feed(saved_feed_id)

        self._tree.blockSignals(False)
        if not restored:
            # Sélectionne "Tous" par défaut
            first = self._tree.topLevelItem(0)
            if first:
                self._tree.setCurrentItem(first)

    def _make_smart_items(self, total_unread: int) -> list[QTreeWidgetItem]:
        items = []
        defs = [
            ("all",       "Tous les articles",    total_unread),
            ("unread",    "Non lus",              total_unread),
            ("favorites", "Favoris",              None),
        ]
        for key, label, unread in defs:
            item = QTreeWidgetItem()
            display = f"{_SMART_ICONS.get(key, '')}  {label}"
            if unread:
                display += f"  ({unread})"
            item.setText(0, display)
            item.setData(0, ROLE_TYPE,  "smart")
            item.setData(0, ROLE_SMART, key)
            font = item.font(0)
            font.setBold(True if unread else False)
            item.setFont(0, font)
            items.append(item)
        return items

    def _make_category_item(self, category: str, cat_feeds: list) -> QTreeWidgetItem:
        # Calcule le total non-lu de la catégorie
        cat_unread = sum(self._unread_counts.get(f["id"], 0) for f in cat_feeds)

        label = f"{_CAT_ICON}  {category}"
        if cat_unread:
            label += f"  ({cat_unread})"

        item = QTreeWidgetItem([label])
        item.setData(0, ROLE_TYPE, "category")
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setForeground(0, QColor("#2c3e50"))
        return item

    def _make_feed_item(self, feed: dict) -> QTreeWidgetItem:
        unread = self._unread_counts.get(feed["id"], 0)
        error  = feed.get("fetch_error")

        icon = _ERROR_ICON if error else _FEED_ICON
        label = f"{icon}  {feed['name']}"
        if unread:
            label += f"  ({unread})"

        item = QTreeWidgetItem([label])
        item.setData(0, ROLE_TYPE,    "feed")
        item.setData(0, ROLE_FEED_ID, feed["id"])

        if unread:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

        if error:
            item.setForeground(0, QColor("#c0392b"))
            item.setToolTip(0, f"Dernière erreur :\n{error}")
        elif not feed.get("active"):
            item.setForeground(0, QColor("#95a5a6"))
            item.setToolTip(0, "Flux désactivé")

        return item

    # ------------------------------------------------------------------
    # Sélection programmatique
    # ------------------------------------------------------------------

    def _select_smart(self, smart: str) -> bool:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.data(0, ROLE_SMART) == smart:
                self._tree.setCurrentItem(item)
                return True
        return False

    def _select_feed(self, feed_id: int) -> bool:
        for i in range(self._tree.topLevelItemCount()):
            cat_item = self._tree.topLevelItem(i)
            if not cat_item:
                continue
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child and child.data(0, ROLE_FEED_ID) == feed_id:
                    self._tree.setCurrentItem(child)
                    return True
        return False

    # ------------------------------------------------------------------
    # Signaux
    # ------------------------------------------------------------------

    def _on_item_changed(self, current: QTreeWidgetItem, _previous):
        if not current:
            return
        item_type = current.data(0, ROLE_TYPE)
        if item_type == "smart":
            self.smart_selected.emit(current.data(0, ROLE_SMART))
        elif item_type == "feed":
            feed_id = current.data(0, ROLE_FEED_ID)
            if feed_id is not None:
                self.feed_selected.emit(feed_id)

    # ------------------------------------------------------------------
    # Menu contextuel
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        menu = QMenu(self)

        # Toujours proposer l'ajout
        action_add = menu.addAction("Ajouter un flux…")
        action_add.triggered.connect(self.add_feed_requested.emit)

        if item:
            item_type = item.data(0, ROLE_TYPE)
            feed_id   = item.data(0, ROLE_FEED_ID)

            if item_type == "feed" and feed_id is not None:
                menu.addSeparator()
                action_refresh = menu.addAction("Rafraîchir ce flux")
                action_refresh.triggered.connect(lambda: self.refresh_feed_requested.emit(feed_id))

                action_mark = menu.addAction("Tout marquer comme lu")
                action_mark.triggered.connect(lambda: self.mark_all_read_feed.emit(feed_id))

                menu.addSeparator()
                action_edit = menu.addAction("Modifier…")
                action_edit.triggered.connect(lambda: self.edit_feed_requested.emit(feed_id))

                action_delete = menu.addAction("Supprimer")
                action_delete.triggered.connect(lambda: self.delete_feed_requested.emit(feed_id))

            elif item_type == "smart" and item.data(0, ROLE_SMART) == "all":
                menu.addSeparator()
                action_mark_all = menu.addAction("Tout marquer comme lu")
                action_mark_all.triggered.connect(lambda: self.mark_all_read_feed.emit(-1))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Helpers publics
    # ------------------------------------------------------------------

    def get_selected_feed_id(self) -> int | None:
        item = self._tree.currentItem()
        if item and item.data(0, ROLE_TYPE) == "feed":
            return item.data(0, ROLE_FEED_ID)
        return None

    def get_selected_smart(self) -> str | None:
        item = self._tree.currentItem()
        if item and item.data(0, ROLE_TYPE) == "smart":
            return item.data(0, ROLE_SMART)
        return None
