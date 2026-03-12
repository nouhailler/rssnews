"""
Barre de contrôle TTS.

Widget compact affiché en bas de la fenêtre principale :
  🔊 TTS  [▶] [⏸] [⏹]  ══════════════  × [1.0]  statut  [⚙]
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from tts.tts_manager import TTSManager
from tts.text_cleaner import clean_to_text

logger = logging.getLogger(__name__)

_BAR_STYLE = "background: #2c3e50;"
_BTN_STYLE = (
    "QPushButton { background:#3d5a73; color:white; border:none; border-radius:3px; }"
    "QPushButton:hover { background:#4a6f8a; }"
    "QPushButton:disabled { color:#555; background:#2c3e50; }"
)
_PROGRESS_STYLE = (
    "QProgressBar { background:#3d5a73; border:none; border-radius:3px; }"
    "QProgressBar::chunk { background:#3498db; border-radius:3px; }"
)


class TTSBar(QWidget):
    """
    Barre de contrôle TTS intégrée en bas de la fenêtre principale.

    Signal :
      model_path_changed(str) — émis quand l'utilisateur choisit un nouveau modèle
    """

    model_path_changed = pyqtSignal(str)

    def __init__(self, model_path: str = "", parent=None):
        super().__init__(parent)
        self._tts = TTSManager(model_path=model_path)
        self._text       = ""
        self._duration_ms = 0
        self._paused     = False

        self.setStyleSheet(_BAR_STYLE)
        self.setFixedHeight(34)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(5)

        # Étiquette
        lbl = QLabel("🔊 TTS")
        lbl.setStyleSheet("font-weight:bold; color:#ecf0f1; font-size:11px;")

        # Boutons de transport
        self._btn_play  = _btn("▶", "Lire l'article (TTS)")
        self._btn_pause = _btn("⏸", "Mettre en pause")
        self._btn_stop  = _btn("⏹", "Arrêter")
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)

        # Barre de progression
        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(_PROGRESS_STYLE)

        # Vitesse
        speed_lbl = QLabel("×")
        speed_lbl.setStyleSheet("color:#bdc3c7; font-size:11px;")
        self._speed_box = QDoubleSpinBox()
        self._speed_box.setRange(0.5, 2.0)
        self._speed_box.setSingleStep(0.1)
        self._speed_box.setValue(1.0)
        self._speed_box.setDecimals(1)
        self._speed_box.setFixedSize(52, 22)
        self._speed_box.setToolTip("Vitesse de synthèse (0.5 – 2.0×)")
        self._speed_box.setStyleSheet("background:#3d5a73; color:white; border:none;")

        # Statut
        self._status = QLabel("—")
        self._status.setStyleSheet("color:#95a5a6; font-size:11px;")
        self._status.setFixedWidth(130)

        # Bouton configuration modèle
        self._btn_cfg = _btn("⚙", "Choisir le modèle Piper (.onnx)", size=22)

        layout.addWidget(lbl)
        layout.addWidget(self._btn_play)
        layout.addWidget(self._btn_pause)
        layout.addWidget(self._btn_stop)
        layout.addWidget(self._progress, 1)
        layout.addWidget(speed_lbl)
        layout.addWidget(self._speed_box)
        layout.addWidget(self._status)
        layout.addWidget(self._btn_cfg)

    def _connect_signals(self):
        self._btn_play.clicked.connect(self._on_play)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_cfg.clicked.connect(self._on_config)
        self._speed_box.valueChanged.connect(self._tts.set_speed)

        t = self._tts
        t.synthesis_started.connect(lambda: self._set_status("Synthèse…"))
        t.synthesis_finished.connect(lambda: self._set_status("Lecture…"))
        t.playback_started.connect(self._on_playback_started)
        t.playback_finished.connect(self._on_playback_finished)
        t.tts_error.connect(self._on_error)
        t.position_changed.connect(self._on_position)
        t.duration_changed.connect(self._on_duration)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_text(self, html_or_text: str):
        """Charge le texte d'un article (nettoyage HTML inclus)."""
        self._tts.stop()
        self._paused = False
        self._text = clean_to_text(html_or_text) if html_or_text else ""
        self._reset_ui()
        self._set_status("Prêt" if self._text else "—")

    def stop(self):
        """Arrêt propre (appelé lors de la fermeture de l'application)."""
        self._tts.stop()

    # ------------------------------------------------------------------
    # Handlers boutons
    # ------------------------------------------------------------------

    def _on_play(self):
        if self._paused:
            self._tts.resume()
            self._paused = False
            self._btn_play.setEnabled(False)
            self._btn_pause.setEnabled(True)
            self._set_status("Lecture…")
        elif self._text:
            self._tts.set_speed(self._speed_box.value())
            self._tts.speak(self._text)
            self._btn_play.setEnabled(False)
            self._set_status("En cours…")

    def _on_pause(self):
        self._tts.pause()
        self._paused = True
        self._btn_play.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._set_status("En pause")

    def _on_stop(self):
        self._tts.stop()
        self._reset_ui()
        self._set_status("Arrêté")

    def _on_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner le modèle Piper",
            str(Path.home()),
            "Modèles Piper (*.onnx);;Tous les fichiers (*)",
        )
        if path:
            self._tts.set_model(path)
            self.model_path_changed.emit(path)
            self._set_status("Modèle chargé")

    # ------------------------------------------------------------------
    # Handlers TTSManager
    # ------------------------------------------------------------------

    def _on_playback_started(self):
        self._btn_play.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._set_status("Lecture…")

    def _on_playback_finished(self):
        self._reset_ui()
        self._set_status("Terminé")

    def _on_error(self, msg: str):
        logger.warning("TTS error: %s", msg)
        self._reset_ui()
        self._set_status("Erreur TTS")
        QMessageBox.warning(self, "Erreur TTS", msg)

    def _on_position(self, pos_ms: int):
        if self._duration_ms > 0:
            self._progress.setValue(int(pos_ms * 1000 / self._duration_ms))

    def _on_duration(self, dur_ms: int):
        self._duration_ms = dur_ms

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_ui(self):
        self._paused      = False
        self._duration_ms = 0
        self._btn_play.setEnabled(bool(self._text))
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._progress.setValue(0)

    def _set_status(self, msg: str):
        self._status.setText(msg)


def _btn(text: str, tooltip: str = "", size: int = 26) -> QPushButton:
    b = QPushButton(text)
    b.setFixedSize(size, 22)
    b.setToolTip(tooltip)
    b.setStyleSheet(_BTN_STYLE)
    return b
