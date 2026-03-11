"""
Boîtes de dialogue de l'application RSS Reader.

  - AddFeedDialog    : ajouter ou modifier un flux
  - SettingsDialog   : préférences de l'application
  - OpmlImportDialog : importer un fichier OPML
  - AboutDialog      : à propos
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout, QCheckBox, QFileDialog, QComboBox,
    QTextEdit, QGroupBox,
)

import database as db
import rss_fetcher as fetcher


# ---------------------------------------------------------------------------
# Thread de validation d'URL
# ---------------------------------------------------------------------------

class _ValidateThread(QThread):
    """Vérifie qu'une URL est un flux RSS valide dans un thread séparé."""

    result_ready = pyqtSignal(bool, str, str)   # (ok, feed_title, error_msg)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            import requests
            response = requests.get(
                self.url,
                timeout=(8, 15),
                headers={"User-Agent": fetcher.USER_AGENT},
                allow_redirects=True,
                verify=True,
            )
            response.raise_for_status()
            import feedparser
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                exc = parsed.get("bozo_exception")
                self.result_ready.emit(False, "", fetcher._parse_error_message(self.url, exc))
                return
            title = parsed.feed.get("title", "") or ""
            self.result_ready.emit(True, title.strip(), "")
        except requests.exceptions.SSLError:
            self.result_ready.emit(False, "", "Erreur SSL : certificat invalide ou expiré.")
        except requests.exceptions.ConnectionError:
            self.result_ready.emit(False, "", "Impossible de se connecter. Vérifiez l'URL et votre connexion.")
        except requests.exceptions.Timeout:
            self.result_ready.emit(False, "", "Délai dépassé. Le serveur ne répond pas.")
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            self.result_ready.emit(False, "", fetcher._http_error_message(code))
        except Exception as exc:
            self.result_ready.emit(False, "", str(exc)[:300])


# ---------------------------------------------------------------------------
# Dialogue Ajouter / Modifier un flux
# ---------------------------------------------------------------------------

class AddFeedDialog(QDialog):
    """
    Dialogue pour ajouter un nouveau flux ou modifier un flux existant.

    Si `feed_data` est fourni, le dialogue est en mode édition.
    """

    def __init__(self, parent=None, feed_data: dict | None = None):
        super().__init__(parent)
        self._feed_data = feed_data
        self._validate_thread: _ValidateThread | None = None
        self._detected_title: str = ""

        is_edit = feed_data is not None
        self.setWindowTitle("Modifier le flux" if is_edit else "Ajouter un flux RSS")
        self.setMinimumWidth(480)
        self._build_ui(is_edit, feed_data)

    def _build_ui(self, is_edit: bool, feed_data: dict | None):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # URL
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/feed.rss")
        self.url_edit.textChanged.connect(self._on_url_changed)
        self._btn_detect = QPushButton("Détecter")
        self._btn_detect.setFixedWidth(80)
        self._btn_detect.setToolTip("Tente de détecter automatiquement le flux RSS de cette page")
        self._btn_detect.clicked.connect(self._on_detect)
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self._btn_detect)
        form.addRow("URL du flux :", url_row)

        # Statut validation
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        form.addRow("", self._status_label)

        # Nom
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nom affiché (auto-détecté si vide)")
        form.addRow("Nom :", self.name_edit)

        # Catégorie
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setPlaceholderText("Général")
        existing_cats = db.get_categories()
        if existing_cats:
            self.category_combo.addItems(existing_cats)
        else:
            self.category_combo.addItem("Général")
        form.addRow("Catégorie :", self.category_combo)

        layout.addLayout(form)

        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setText("Enregistrer" if is_edit else "Ajouter")
        layout.addWidget(buttons)

        # Pré-remplissage en mode édition
        if feed_data:
            self.url_edit.setText(feed_data.get("url", ""))
            self.name_edit.setText(feed_data.get("name", ""))
            cat = feed_data.get("category", "Général")
            idx = self.category_combo.findText(cat)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setEditText(cat)

    def _on_url_changed(self, text: str):
        self._status_label.clear()
        self._detected_title = ""

    def _on_detect(self):
        url = self.url_edit.text().strip()
        if not url:
            self._set_status("Entrez d'abord une URL.", error=True)
            return
        if not url.startswith(("http://", "https://")):
            self._set_status("L'URL doit commencer par http:// ou https://", error=True)
            return

        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("...")
        self._set_status("Vérification en cours…", error=False)

        self._validate_thread = _ValidateThread(url)
        self._validate_thread.result_ready.connect(self._on_validate_result)
        self._validate_thread.start()

    def _on_validate_result(self, ok: bool, feed_title: str, error_msg: str):
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("Détecter")
        if ok:
            self._detected_title = feed_title
            if feed_title and not self.name_edit.text().strip():
                self.name_edit.setText(feed_title)
            self._set_status(
                f"Flux valide ! Titre détecté : « {feed_title or '(sans titre)'} »",
                error=False,
            )
        else:
            self._set_status(error_msg, error=True)

    def _set_status(self, msg: str, error: bool = False):
        color = "#c0392b" if error else "#27ae60"
        self._status_label.setText(f'<span style="color:{color}">{msg}</span>')

    def _on_accept(self):
        url = self.url_edit.text().strip()
        name = self.name_edit.text().strip()
        category = self.category_combo.currentText().strip() or "Général"

        if not url:
            QMessageBox.warning(self, "Champ requis", "Veuillez entrer l'URL du flux.")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self, "URL invalide",
                "L'URL doit commencer par http:// ou https://",
            )
            return
        if not name:
            name = self._detected_title or url

        self._result = {"url": url, "name": name, "category": category}
        self.accept()

    def get_feed_data(self) -> dict:
        """Retourne les données saisies (url, name, category)."""
        return getattr(self, "_result", {})


# ---------------------------------------------------------------------------
# Dialogue Préférences
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")
        self.setMinimumWidth(420)
        self._settings = settings or {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Mise à jour automatique
        grp_update = QGroupBox("Mise à jour automatique")
        grp_layout = QFormLayout(grp_update)

        self._auto_update = QCheckBox("Activer la mise à jour automatique")
        self._auto_update.setChecked(self._settings.get("auto_update", True))
        grp_layout.addRow(self._auto_update)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 240)
        self._interval_spin.setSuffix(" minutes")
        self._interval_spin.setValue(self._settings.get("update_interval", 30))
        grp_layout.addRow("Intervalle :", self._interval_spin)

        layout.addWidget(grp_update)

        # Affichage
        grp_display = QGroupBox("Affichage")
        grp_d_layout = QFormLayout(grp_display)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 24)
        self._font_size.setSuffix(" px")
        self._font_size.setValue(self._settings.get("font_size", 14))
        grp_d_layout.addRow("Taille de police :", self._font_size)

        self._mark_read_on_open = QCheckBox("Marquer comme lu à l'ouverture")
        self._mark_read_on_open.setChecked(self._settings.get("mark_read_on_open", True))
        grp_d_layout.addRow(self._mark_read_on_open)

        layout.addWidget(grp_display)

        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        self._result = {
            "auto_update":        self._auto_update.isChecked(),
            "update_interval":    self._interval_spin.value(),
            "font_size":          self._font_size.value(),
            "mark_read_on_open":  self._mark_read_on_open.isChecked(),
        }
        self.accept()

    def get_settings(self) -> dict:
        return getattr(self, "_result", self._settings)


# ---------------------------------------------------------------------------
# Dialogue Import OPML
# ---------------------------------------------------------------------------

class OpmlImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer des flux (OPML)")
        self.setMinimumWidth(500)
        self._file_path: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        desc = QLabel(
            "Importez un fichier OPML pour ajouter plusieurs flux en une seule opération.\n"
            "Les flux déjà présents seront ignorés."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        file_row = QHBoxLayout()
        self._file_label = QLabel("Aucun fichier sélectionné")
        self._file_label.setStyleSheet("color: gray; font-style: italic;")
        btn_browse = QPushButton("Parcourir…")
        btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self._file_label, 1)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("Aperçu des flux à importer…")
        self._preview.setMaximumHeight(200)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Importer")
        self._ok_btn.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un fichier OPML", "", "Fichiers OPML (*.opml *.xml);;Tous les fichiers (*)"
        )
        if not path:
            return
        try:
            feeds = fetcher.parse_opml(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Erreur OPML", str(exc))
            return

        self._file_path = path
        self._parsed_feeds = feeds
        self._file_label.setText(path)
        self._file_label.setStyleSheet("")

        lines = [f"  • [{f['category']}] {f['name']}  ({f['url']})" for f in feeds]
        self._preview.setText(f"{len(feeds)} flux trouvés :\n" + "\n".join(lines[:100]))
        self._ok_btn.setEnabled(bool(feeds))

    def get_feeds(self) -> list[dict]:
        return getattr(self, "_parsed_feeds", [])


# ---------------------------------------------------------------------------
# Dialogue À propos
# ---------------------------------------------------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("À propos de RSS Reader")
        self.setFixedSize(360, 220)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("<h2>RSS Reader</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "Lecteur de flux RSS/Atom pour Linux\n\n"
            "Version 0.1\n"
            "Licence MIT\n\n"
            "Python · PyQt6 · feedparser · SQLite"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        btn = QPushButton("Fermer")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------------------
# Dialogue de progression lors du rafraîchissement
# ---------------------------------------------------------------------------

class RefreshProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mise à jour des flux…")
        self.setMinimumWidth(380)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        layout = QVBoxLayout(self)

        self._feed_label = QLabel("Initialisation…")
        layout.addWidget(self._feed_label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        layout.addWidget(self._bar)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        layout.addWidget(self._log)

        self._close_btn = QPushButton("Fermer")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        layout.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def set_progress(self, current: int, total: int, feed_name: str):
        percent = int(current / total * 100) if total else 0
        self._bar.setValue(percent)
        self._feed_label.setText(f"Récupération {current}/{total} : {feed_name}")

    def append_log(self, message: str, error: bool = False):
        color = "#c0392b" if error else "#27ae60"
        self._log.append(f'<span style="color:{color}">{message}</span>')

    def finish(self, summary: str):
        self._feed_label.setText(summary)
        self._bar.setValue(100)
        self._close_btn.setEnabled(True)
