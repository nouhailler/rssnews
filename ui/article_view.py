"""
Panneau droit : affichage du contenu d'un article.

Utilise QTextBrowser pour un rendu HTML sécurisé
(JavaScript désactivé, ressources externes bloquées).
"""

from __future__ import annotations

import subprocess
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import database as db


class ArticleView(QWidget):
    """
    Panneau d'affichage d'un article.

    Affiche :
      - Titre
      - Source et date
      - Boutons (favori, ouvrir dans navigateur, marquer lu/non-lu)
      - Contenu HTML ou texte brut
    """

    def __init__(self, font_size: int = 14, parent=None):
        super().__init__(parent)
        self._article_id: int | None = None
        self._font_size = font_size
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Barre d'en-tête ----------------------------------------
        header_widget = QWidget()
        header_widget.setStyleSheet("background: #ecf0f1; border-bottom: 1px solid #bdc3c7;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 4, 8, 4)

        # Boutons d'action
        self._btn_favorite = QPushButton("⭐ Favori")
        self._btn_favorite.setCheckable(True)
        self._btn_favorite.setFixedWidth(90)
        self._btn_favorite.toggled.connect(self._on_toggle_favorite)

        self._btn_read = QPushButton("✓ Lu")
        self._btn_read.setCheckable(True)
        self._btn_read.setFixedWidth(70)
        self._btn_read.toggled.connect(self._on_toggle_read)

        self._btn_open = QPushButton("🌐 Ouvrir")
        self._btn_open.setFixedWidth(80)
        self._btn_open.setToolTip("Ouvrir l'article dans le navigateur")
        self._btn_open.clicked.connect(self._on_open_browser)

        # Zoom
        self._btn_zoom_in  = QPushButton("A+")
        self._btn_zoom_out = QPushButton("A-")
        self._btn_zoom_in.setFixedWidth(32)
        self._btn_zoom_out.setFixedWidth(32)
        self._btn_zoom_in.clicked.connect(self._zoom_in)
        self._btn_zoom_out.clicked.connect(self._zoom_out)

        header_layout.addWidget(self._btn_favorite)
        header_layout.addWidget(self._btn_read)
        header_layout.addStretch()
        header_layout.addWidget(self._btn_zoom_out)
        header_layout.addWidget(self._btn_zoom_in)
        header_layout.addWidget(self._btn_open)

        layout.addWidget(header_widget)

        # --- Zone de contenu ----------------------------------------
        self._content_area = QWidget()
        content_layout = QVBoxLayout(self._content_area)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(8)

        # Titre
        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setTextFormat(Qt.TextFormat.RichText)
        self._title_label.setStyleSheet(
            f"font-size: {self._font_size + 4}px; font-weight: bold; color: #2c3e50;"
        )
        content_layout.addWidget(self._title_label)

        # Meta (source + date)
        self._meta_label = QLabel()
        self._meta_label.setWordWrap(True)
        self._meta_label.setStyleSheet(
            "font-size: 11px; color: #7f8c8d; font-style: italic;"
        )
        content_layout.addWidget(self._meta_label)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #ecf0f1;")
        content_layout.addWidget(sep)

        # Corps de l'article (rendu HTML sécurisé)
        self._body = QTextBrowser()
        self._body.setOpenLinks(False)                     # on gère les liens nous-mêmes
        self._body.setOpenExternalLinks(False)
        self._body.anchorClicked.connect(self._on_link_clicked)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setStyleSheet(
            f"font-size: {self._font_size}px; line-height: 1.6; background: white;"
        )
        # Empêche le chargement des ressources externes (images distantes, etc.)
        self._body.document().setMetaInformation(
            self._body.document().MetaInformation.DocumentUrl, "about:blank"
        )
        content_layout.addWidget(self._body, 1)

        # Lien original en bas
        self._link_label = QLabel()
        self._link_label.setWordWrap(True)
        self._link_label.setTextFormat(Qt.TextFormat.RichText)
        self._link_label.setOpenExternalLinks(False)
        self._link_label.linkActivated.connect(self._on_open_browser)
        self._link_label.setStyleSheet("font-size: 11px; color: #3498db; padding-top: 4px;")
        content_layout.addWidget(self._link_label)

        # ScrollArea pour le tout
        scroll = QScrollArea()
        scroll.setWidget(self._content_area)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll, 1)

        # Message "pas d'article sélectionné"
        self._empty_label = QLabel("Sélectionnez un article pour le lire")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: #bdc3c7; font-size: 15px; background: white;"
        )
        layout.addWidget(self._empty_label)

        self._show_empty(True)

    # ------------------------------------------------------------------
    # Chargement d'un article
    # ------------------------------------------------------------------

    def load_article(self, article_id: int):
        """Charge et affiche un article depuis la base de données."""
        art = db.get_article(article_id)
        if not art:
            self.clear()
            return

        self._article_id  = article_id
        self._article_url = art.get("link", "") or ""

        # En-tête
        title = art.get("title") or "(sans titre)"
        self._title_label.setText(f"<b>{_escape(title)}</b>")

        source    = art.get("feed_name", "")
        author    = art.get("author", "")
        pub_date  = _format_date(art.get("published_date") or art.get("fetch_date", ""))
        meta_parts = [p for p in [source, author, pub_date] if p]
        self._meta_label.setText("  |  ".join(meta_parts))

        # Contenu
        content = art.get("content") or ""
        summary = art.get("summary") or ""

        if content and _looks_like_html(content):
            html = _sanitize_html(content)
        elif summary and _looks_like_html(summary):
            html = _sanitize_html(summary)
        elif content:
            html = _text_to_html(content)
        elif summary:
            html = _text_to_html(summary)
        else:
            html = "<p><em>Aucun contenu disponible pour cet article.</em></p>"

        self._body.setHtml(_wrap_html(html, self._font_size))

        # Lien
        if self._article_url:
            self._link_label.setText(
                f'<a href="{_escape(self._article_url)}">Lire l\'article sur le site original</a>'
            )
            self._btn_open.setEnabled(True)
        else:
            self._link_label.clear()
            self._btn_open.setEnabled(False)

        # Boutons état
        self._btn_read.blockSignals(True)
        self._btn_favorite.blockSignals(True)
        self._btn_read.setChecked(bool(art.get("read_status")))
        self._btn_favorite.setChecked(bool(art.get("favorite")))
        self._btn_read.blockSignals(False)
        self._btn_favorite.blockSignals(False)
        self._update_button_styles()

        self._show_empty(False)

    def clear(self):
        """Affiche le message vide."""
        self._article_id  = None
        self._article_url = ""
        self._title_label.clear()
        self._meta_label.clear()
        self._body.clear()
        self._link_label.clear()
        self._show_empty(True)

    def _show_empty(self, empty: bool):
        self._content_area.setVisible(not empty)
        self._empty_label.setVisible(empty)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_toggle_favorite(self, checked: bool):
        if self._article_id is None:
            return
        db.set_article_favorite(self._article_id, checked)
        self._update_button_styles()

    def _on_toggle_read(self, checked: bool):
        if self._article_id is None:
            return
        db.set_article_read(self._article_id, checked)
        self._update_button_styles()

    def _on_open_browser(self, _url=None):
        url = self._article_url
        if url:
            _open_url(url)

    def _on_link_clicked(self, url: QUrl):
        _open_url(url.toString())

    def _zoom_in(self):
        self._font_size = min(self._font_size + 1, 28)
        self._apply_font_size()

    def _zoom_out(self):
        self._font_size = max(self._font_size - 1, 8)
        self._apply_font_size()

    def _apply_font_size(self):
        self._title_label.setStyleSheet(
            f"font-size: {self._font_size + 4}px; font-weight: bold; color: #2c3e50;"
        )
        self._body.setStyleSheet(
            f"font-size: {self._font_size}px; line-height: 1.6; background: white;"
        )
        if self._article_id:
            self.load_article(self._article_id)

    def _update_button_styles(self):
        if self._btn_favorite.isChecked():
            self._btn_favorite.setStyleSheet("color: #e67e22; font-weight: bold;")
            self._btn_favorite.setText("⭐ Favori")
        else:
            self._btn_favorite.setStyleSheet("")
            self._btn_favorite.setText("☆ Favori")

        if self._btn_read.isChecked():
            self._btn_read.setStyleSheet("color: #27ae60;")
            self._btn_read.setText("✓ Lu")
        else:
            self._btn_read.setStyleSheet("color: #7f8c8d;")
            self._btn_read.setText("○ Non lu")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def mark_as_read(self):
        """Marque l'article courant comme lu (appelé depuis l'extérieur)."""
        if self._article_id is None:
            return
        db.set_article_read(self._article_id, True)
        self._btn_read.blockSignals(True)
        self._btn_read.setChecked(True)
        self._btn_read.blockSignals(False)
        self._update_button_styles()

    def get_current_article_id(self) -> int | None:
        return self._article_id


# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Échappe les caractères spéciaux HTML."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _looks_like_html(text: str) -> bool:
    """Détecte si un texte contient du HTML."""
    return "<" in text and ">" in text and any(
        tag in text.lower() for tag in ("<p", "<div", "<br", "<a ", "<img", "<ul", "<ol", "<h")
    )


def _sanitize_html(html: str) -> str:
    """
    Nettoyage minimaliste du HTML :
      - Supprime les balises <script> et <style>
      - Supprime les attributs on* (JavaScript inline)
      - Supprime les liens javascript:
    """
    import re
    # Suppression scripts / styles
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>",  "", html, flags=re.IGNORECASE | re.DOTALL)
    # Suppression attributs on*
    html = re.sub(r'\s+on\w+\s*=\s*"[^"]*"',  "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s+on\w+\s*=\s*'[^']*'",  "", html, flags=re.IGNORECASE)
    # Suppression liens javascript:
    html = re.sub(r'href\s*=\s*"javascript:[^"]*"', 'href="#"', html, flags=re.IGNORECASE)
    return html


def _text_to_html(text: str) -> str:
    """Convertit du texte brut en HTML lisible (paragraphes)."""
    paragraphs = text.split("\n\n")
    html_parts = [f"<p>{_escape(p.strip()).replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()]
    return "\n".join(html_parts)


def _wrap_html(body: str, font_size: int) -> str:
    """Enveloppe le corps HTML dans un document complet avec styles."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: {font_size}px;
    line-height: 1.7;
    color: #2c3e50;
    margin: 0;
    padding: 0;
    background: white;
  }}
  a {{ color: #3498db; }}
  img {{ max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }}
  blockquote {{
    border-left: 4px solid #3498db;
    margin: 12px 0;
    padding: 4px 16px;
    color: #7f8c8d;
    background: #f8f9fa;
  }}
  pre, code {{
    background: #f4f4f4;
    border-radius: 4px;
    padding: 2px 6px;
    font-family: 'Courier New', monospace;
    font-size: {font_size - 1}px;
  }}
  pre {{ padding: 12px; overflow-x: auto; }}
  h1, h2, h3 {{ color: #2c3e50; margin-top: 16px; }}
  p {{ margin: 8px 0; }}
  ul, ol {{ padding-left: 20px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str[:19])
        return dt.strftime("%d/%m/%Y à %H:%M")
    except Exception:
        return date_str[:16] if len(date_str) >= 16 else date_str


def _open_url(url: str):
    try:
        subprocess.Popen(["xdg-open", url])
    except Exception:
        pass
