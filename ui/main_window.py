"""
Fenêtre principale de l'application RSS Reader.

Layout trois panneaux :
  Gauche  : FeedPanel    (arborescence des flux)
  Centre  : ArticleListPanel (liste des articles)
  Droite  : ArticleView  (lecture d'un article)

Gestion :
  - Barre de menus
  - Barre de statut
  - Rafraîchissement automatique (QTimer)
  - Thread de mise à jour en arrière-plan
  - Sauvegarde/restauration de la configuration (JSON)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import database as db
import rss_fetcher as fetcher

from ui.feed_panel    import FeedPanel
from ui.article_list  import ArticleListPanel
from ui.article_view  import ArticleView
from ui.dialogs import (
    AboutDialog,
    AddFeedDialog,
    OpmlImportDialog,
    RefreshProgressDialog,
    SettingsDialog,
)

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path.home() / ".local" / "share" / "rss-reader" / "settings.json"

DEFAULT_SETTINGS = {
    "auto_update":       True,
    "update_interval":   30,      # minutes
    "font_size":         14,
    "mark_read_on_open": True,
    "window_geometry":   None,
    "splitter_sizes":    [220, 320, 600],
}


# ---------------------------------------------------------------------------
# Thread de rafraîchissement RSS (non bloquant)
# ---------------------------------------------------------------------------

class RefreshThread(QThread):
    """Exécute fetch_all_feeds() dans un thread séparé."""

    progress = pyqtSignal(int, int, str)         # (current, total, feed_name)
    finished = pyqtSignal(object)                 # FetchReport

    def __init__(self, feed_id: int | None = None):
        super().__init__()
        self._feed_id = feed_id   # None = tous les flux

    def run(self):
        if self._feed_id is not None:
            result = fetcher.fetch_single_feed(self._feed_id)
            report = fetcher.FetchReport(results=[result])
        else:
            report = fetcher.fetch_all_feeds(progress_callback=self.progress.emit)
        self.finished.emit(report)


# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings = _load_settings()
        self._refresh_thread: RefreshThread | None = None
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._on_auto_refresh)

        self.setWindowTitle("RSS Reader")
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._restore_geometry()
        self._connect_signals()

        # Chargement initial
        self._feed_panel.load()
        self._update_auto_timer()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._feed_panel    = FeedPanel()
        self._article_list  = ArticleListPanel()
        self._article_view  = ArticleView(font_size=self._settings["font_size"])

        sizes = self._settings.get("splitter_sizes", DEFAULT_SETTINGS["splitter_sizes"])
        self._splitter.addWidget(self._feed_panel)
        self._splitter.addWidget(self._article_list)
        self._splitter.addWidget(self._article_view)
        self._splitter.setSizes(sizes)
        self._splitter.setChildrenCollapsible(False)

        layout.addWidget(self._splitter)

    def _build_menu(self):
        menubar = self.menuBar()

        # --- Fichier --------------------------------------------------
        file_menu = menubar.addMenu("Fichier")

        act_add = file_menu.addAction("Ajouter un flux…")
        act_add.setShortcut("Ctrl+N")
        act_add.triggered.connect(self._on_add_feed)

        file_menu.addSeparator()

        act_import = file_menu.addAction("Importer OPML…")
        act_import.triggered.connect(self._on_import_opml)

        act_export = file_menu.addAction("Exporter OPML…")
        act_export.triggered.connect(self._on_export_opml)

        file_menu.addSeparator()

        act_quit = file_menu.addAction("Quitter")
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)

        # --- Vue ------------------------------------------------------
        view_menu = menubar.addMenu("Vue")

        act_refresh = view_menu.addAction("Rafraîchir tous les flux")
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(lambda: self._on_refresh(feed_id=None))

        act_mark_all = view_menu.addAction("Tout marquer comme lu")
        act_mark_all.triggered.connect(self._on_mark_all_read_global)

        view_menu.addSeparator()

        act_prefs = view_menu.addAction("Préférences…")
        act_prefs.setShortcut("Ctrl+,")
        act_prefs.triggered.connect(self._on_settings)

        # --- Aide -----------------------------------------------------
        help_menu = menubar.addMenu("Aide")
        act_about = help_menu.addAction("À propos…")
        act_about.triggered.connect(self._on_about)

    def _build_toolbar(self):
        tb = QToolBar("Outils")
        tb.setMovable(False)
        self.addToolBar(tb)

        btn_add = tb.addAction("➕ Ajouter flux")
        btn_add.triggered.connect(self._on_add_feed)

        btn_refresh = tb.addAction("🔄 Rafraîchir")
        btn_refresh.setToolTip("Rafraîchir tous les flux (F5)")
        btn_refresh.triggered.connect(lambda: self._on_refresh(feed_id=None))

        tb.addSeparator()

        self._refresh_status_label = QLabel("  ")
        tb.addWidget(self._refresh_status_label)

    def _build_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel("")
        self._statusbar.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Connexions des signaux
    # ------------------------------------------------------------------

    def _connect_signals(self):
        fp = self._feed_panel
        fp.feed_selected.connect(self._on_feed_selected)
        fp.smart_selected.connect(self._on_smart_selected)
        fp.add_feed_requested.connect(self._on_add_feed)
        fp.edit_feed_requested.connect(self._on_edit_feed)
        fp.delete_feed_requested.connect(self._on_delete_feed)
        fp.refresh_feed_requested.connect(self._on_refresh)
        fp.mark_all_read_feed.connect(self._on_mark_all_read_feed)

        self._article_list.article_selected.connect(self._on_article_selected)

    # ------------------------------------------------------------------
    # Sélection
    # ------------------------------------------------------------------

    def _on_feed_selected(self, feed_id: int):
        self._article_list.load_feed(feed_id)
        self._article_view.clear()

    def _on_smart_selected(self, smart: str):
        self._article_list.load_smart(smart)
        self._article_view.clear()

    def _on_article_selected(self, article_id: int):
        self._article_view.load_article(article_id)
        if self._settings.get("mark_read_on_open", True):
            self._article_list.mark_current_as_read()
            self._article_view.mark_as_read()
        # Met à jour les compteurs dans le panneau flux
        self._feed_panel.load()
        # Restaure la sélection de flux
        feed_id = self._feed_panel.get_selected_feed_id()
        smart   = self._feed_panel.get_selected_smart()
        if feed_id:
            self._feed_panel.load()
        elif smart:
            self._feed_panel.load()

    # ------------------------------------------------------------------
    # Gestion des flux (CRUD)
    # ------------------------------------------------------------------

    def _on_add_feed(self):
        dlg = AddFeedDialog(self)
        if dlg.exec():
            data = dlg.get_feed_data()
            try:
                db.add_feed(data["name"], data["url"], data["category"])
                self._feed_panel.load()
                self._set_status(f"Flux « {data['name']} » ajouté.")
                # Lance un rafraîchissement du nouveau flux
                feed = next(
                    (f for f in db.get_all_feeds() if f["url"] == data["url"]),
                    None,
                )
                if feed:
                    self._on_refresh(feed["id"])
            except Exception as exc:
                if "UNIQUE constraint" in str(exc):
                    QMessageBox.warning(self, "Flux dupliqué", "Ce flux est déjà dans votre liste.")
                else:
                    QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter le flux :\n{exc}")

    def _on_edit_feed(self, feed_id: int):
        feed = db.get_feed(feed_id)
        if not feed:
            return
        dlg = AddFeedDialog(self, feed_data=feed)
        if dlg.exec():
            data = dlg.get_feed_data()
            db.update_feed(feed_id, data["name"], data["url"], data["category"])
            self._feed_panel.load()
            self._set_status(f"Flux « {data['name']} » modifié.")

    def _on_delete_feed(self, feed_id: int):
        feed = db.get_feed(feed_id)
        if not feed:
            return
        reply = QMessageBox.question(
            self,
            "Supprimer le flux",
            f"Supprimer définitivement le flux « {feed['name']} » et tous ses articles ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_feed(feed_id)
            self._feed_panel.load()
            self._article_list.load_smart("all")
            self._article_view.clear()
            self._set_status(f"Flux « {feed['name']} » supprimé.")

    # ------------------------------------------------------------------
    # Rafraîchissement RSS
    # ------------------------------------------------------------------

    def _on_refresh(self, feed_id: int | None = None):
        if self._refresh_thread and self._refresh_thread.isRunning():
            self._set_status("Mise à jour déjà en cours…")
            return

        # Dialogue de progression pour la mise à jour globale
        if feed_id is None:
            self._progress_dlg = RefreshProgressDialog(self)
            self._progress_dlg.show()
        else:
            self._progress_dlg = None
            self._set_status("Mise à jour en cours…")

        self._refresh_thread = RefreshThread(feed_id=feed_id)
        self._refresh_thread.progress.connect(self._on_refresh_progress)
        self._refresh_thread.finished.connect(self._on_refresh_finished)
        self._refresh_status_label.setText(" 🔄 Mise à jour…")
        self._refresh_thread.start()

    def _on_refresh_progress(self, current: int, total: int, feed_name: str):
        if self._progress_dlg:
            self._progress_dlg.set_progress(current, total, feed_name)

    def _on_refresh_finished(self, report: fetcher.FetchReport):
        self._refresh_status_label.setText("  ")
        self._feed_panel.load()

        # Recharge la liste si elle est visible
        feed_id = self._feed_panel.get_selected_feed_id()
        smart   = self._feed_panel.get_selected_smart()
        if feed_id:
            self._article_list.refresh()
        elif smart:
            self._article_list.refresh()

        # Bilan
        new_total = report.total_new
        errors    = report.failures

        summary = f"{new_total} nouvel{'s' if new_total > 1 else ''} article{'s' if new_total > 1 else ''}"
        if errors:
            summary += f" — {len(errors)} erreur{'s' if len(errors) > 1 else ''}"

        if self._progress_dlg:
            for r in report.results:
                if r.success:
                    self._progress_dlg.append_log(
                        f"✓ {r.feed_name} : {r.new_articles} nouveau(x)", error=False
                    )
                else:
                    self._progress_dlg.append_log(
                        f"✗ {r.feed_name} : {r.error_message}", error=True
                    )
            self._progress_dlg.finish(summary)
        else:
            self._set_status(summary)

        # Notification des erreurs en mode flux unique
        if errors and not self._progress_dlg:
            err = errors[0]
            QMessageBox.warning(
                self,
                f"Erreur — {err.feed_name}",
                err.error_message,
            )

    def _on_auto_refresh(self):
        logger.debug("Auto-refresh déclenché")
        self._on_refresh(feed_id=None)

    # ------------------------------------------------------------------
    # Marquage global
    # ------------------------------------------------------------------

    def _on_mark_all_read_global(self):
        db.mark_all_read()
        self._feed_panel.load()
        self._article_list.refresh()
        self._set_status("Tous les articles marqués comme lus.")

    def _on_mark_all_read_feed(self, feed_id: int):
        if feed_id == -1:
            db.mark_all_read()
        else:
            db.mark_all_read(feed_id)
        self._feed_panel.load()
        self._article_list.refresh()

    # ------------------------------------------------------------------
    # Import / Export OPML
    # ------------------------------------------------------------------

    def _on_import_opml(self):
        dlg = OpmlImportDialog(self)
        if dlg.exec():
            feeds = dlg.get_feeds()
            added = db.import_opml(feeds)
            self._feed_panel.load()
            QMessageBox.information(
                self, "Import OPML",
                f"{added} flux importé{'s' if added > 1 else ''} sur {len(feeds)} trouvé{'s' if len(feeds) > 1 else ''}."
            )
            if added:
                self._on_refresh(feed_id=None)

    def _on_export_opml(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en OPML", "flux_rss.opml",
            "Fichiers OPML (*.opml *.xml);;Tous les fichiers (*)"
        )
        if not path:
            return
        try:
            fetcher.export_opml(path)
            self._set_status(f"Export OPML enregistré : {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'export", str(exc))

    # ------------------------------------------------------------------
    # Préférences
    # ------------------------------------------------------------------

    def _on_settings(self):
        dlg = SettingsDialog(self, settings=self._settings)
        if dlg.exec():
            self._settings.update(dlg.get_settings())
            _save_settings(self._settings)
            self._update_auto_timer()
            self._article_view._font_size = self._settings["font_size"]
            self._set_status("Préférences enregistrées.")

    def _update_auto_timer(self):
        self._auto_timer.stop()
        if self._settings.get("auto_update", True):
            interval_ms = self._settings.get("update_interval", 30) * 60 * 1000
            self._auto_timer.start(interval_ms)

    # ------------------------------------------------------------------
    # À propos
    # ------------------------------------------------------------------

    def _on_about(self):
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Géométrie / état
    # ------------------------------------------------------------------

    def _restore_geometry(self):
        geom = self._settings.get("window_geometry")
        if geom:
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(bytes(geom, "ascii")))
            except Exception:
                self.resize(1200, 750)
        else:
            self.resize(1200, 750)

    def closeEvent(self, event):
        # Sauvegarde géométrie et état des splitters
        self._settings["window_geometry"] = bytes(self.saveGeometry().toHex()).decode("ascii")
        self._settings["splitter_sizes"]  = self._splitter.sizes()
        _save_settings(self._settings)
        # Arrêt propre du thread de rafraîchissement
        if self._refresh_thread and self._refresh_thread.isRunning():
            self._refresh_thread.wait(3000)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        self._status_label.setText(msg)


# ---------------------------------------------------------------------------
# Persistance des paramètres
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            settings.update(loaded)
        except Exception:
            pass
    return settings


def _save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
