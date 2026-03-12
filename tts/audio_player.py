"""
Lecteur audio dans un QThread séparé.

Utilise `aplay` (ALSA) via subprocess.
Pause/reprise via SIGSTOP/SIGCONT (Linux uniquement).
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
import wave

from PyQt6.QtCore import QThread, pyqtSignal


class AudioPlayer(QThread):
    """
    Joue un fichier WAV dans un thread séparé via aplay.

    Signaux :
      playback_started   — aplay a démarré
      playback_finished  — lecture terminée normalement
      playback_error(str)— erreur
      position_changed(int) — position courante en ms
      duration_changed(int) — durée totale en ms
    """

    playback_started  = pyqtSignal()
    playback_finished = pyqtSignal()
    playback_error    = pyqtSignal(str)
    position_changed  = pyqtSignal(int)
    duration_changed  = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path: str | None = None
        self._proc: subprocess.Popen | None = None
        self._paused = False
        self._stop_flag = False
        self._duration_ms = 0

    def set_file(self, path: str):
        self._path = path
        self._paused = False
        self._stop_flag = False

    # ------------------------------------------------------------------
    # Thread principal
    # ------------------------------------------------------------------

    def run(self):
        if not self._path:
            return

        # Durée totale depuis l'en-tête WAV
        try:
            self._duration_ms = _wav_duration_ms(self._path)
            self.duration_changed.emit(self._duration_ms)
        except Exception:
            self._duration_ms = 0

        # Lancement de aplay
        try:
            self._proc = subprocess.Popen(
                ["aplay", self._path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            self.playback_error.emit(
                "aplay non trouvé. Installez alsa-utils :\n  sudo apt install alsa-utils"
            )
            return

        self.playback_started.emit()

        start_ms = _now_ms()
        total_paused_ms = 0
        pause_start_ms: int | None = None

        while self._proc.poll() is None:
            if self._stop_flag:
                self._proc.terminate()
                self._proc.wait()
                return

            if self._paused:
                if pause_start_ms is None:
                    pause_start_ms = _now_ms()
            else:
                if pause_start_ms is not None:
                    total_paused_ms += _now_ms() - pause_start_ms
                    pause_start_ms = None
                elapsed = _now_ms() - start_ms - total_paused_ms
                if self._duration_ms > 0:
                    self.position_changed.emit(min(elapsed, self._duration_ms))

            time.sleep(0.1)

        # Vérification code retour
        if self._proc.returncode not in (0, -signal.SIGTERM):
            stderr = (self._proc.stderr.read() or b"").decode(errors="replace")
            if stderr:
                self.playback_error.emit(f"aplay : {stderr.strip()}")
                return

        self.playback_finished.emit()

    # ------------------------------------------------------------------
    # Contrôles (appelés depuis le thread Qt principal)
    # ------------------------------------------------------------------

    def pause(self):
        if self._proc and self._proc.poll() is None and not self._paused:
            try:
                os.kill(self._proc.pid, signal.SIGSTOP)
                self._paused = True
            except (ProcessLookupError, PermissionError):
                pass

    def resume(self):
        if self._proc and self._proc.poll() is None and self._paused:
            try:
                os.kill(self._proc.pid, signal.SIGCONT)
                self._paused = False
            except (ProcessLookupError, PermissionError):
                pass

    def stop(self):
        self._stop_flag = True
        if self._proc and self._proc.poll() is None:
            try:
                if self._paused:
                    os.kill(self._proc.pid, signal.SIGCONT)
                self._proc.terminate()
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wav_duration_ms(path: str) -> int:
    with wave.open(path, "rb") as w:
        return int(w.getnframes() / w.getframerate() * 1000)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
