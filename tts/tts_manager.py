"""
Gestionnaire TTS principal.

Flux complet :
  texte propre → hash MD5 → cache WAV → (si absent) Piper TTS → aplay

Cache : ~/.local/share/rss-reader/audio_cache/<md5>.wav
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from tts.audio_player import AudioPlayer

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".local" / "share" / "rss-reader" / "audio_cache"


# ---------------------------------------------------------------------------
# Thread de synthèse Piper
# ---------------------------------------------------------------------------

class _SynthesisThread(QThread):
    finished = pyqtSignal(str)   # chemin WAV
    error    = pyqtSignal(str)

    def __init__(self, text: str, output: Path, model: str, speed: float):
        super().__init__()
        self._text   = text
        self._output = output
        self._model  = model
        self._speed  = speed

    def run(self):
        # Écriture dans un fichier temporaire puis renommage atomique
        tmp = self._output.with_suffix(".tmp")
        cmd = ["piper", "--model", self._model, "--output_file", str(tmp)]
        if abs(self._speed - 1.0) > 0.01:
            # length_scale inverse la vitesse : 0.5 = 2× plus rapide
            cmd += ["--length-scale", f"{1.0 / self._speed:.3f}"]

        try:
            result = subprocess.run(
                cmd,
                input=self._text.encode("utf-8"),
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError:
            tmp.unlink(missing_ok=True)
            self.error.emit(
                "Piper TTS introuvable dans le PATH.\n"
                "Installation : https://github.com/rhasspy/piper/releases"
            )
            return
        except subprocess.TimeoutExpired:
            tmp.unlink(missing_ok=True)
            self.error.emit("Synthèse trop longue (timeout 120 s).")
            return
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            self.error.emit(f"Erreur inattendue : {exc}")
            return

        if result.returncode != 0:
            tmp.unlink(missing_ok=True)
            msg = result.stderr.decode(errors="replace").strip()
            self.error.emit(msg or f"Piper a échoué (code {result.returncode}).")
            return

        try:
            tmp.rename(self._output)
        except OSError as exc:
            self.error.emit(f"Impossible de sauvegarder le fichier audio : {exc}")
            return

        self.finished.emit(str(self._output))


# ---------------------------------------------------------------------------
# Gestionnaire principal
# ---------------------------------------------------------------------------

class TTSManager(QObject):
    """
    Orchestre la synthèse Piper et la lecture audio.

    Utilisation :
        mgr = TTSManager(model_path="/chemin/vers/modele.onnx")
        mgr.speak("Texte à lire")
        mgr.pause()
        mgr.resume()
        mgr.stop()
    """

    synthesis_started  = pyqtSignal()
    synthesis_finished = pyqtSignal()
    playback_started   = pyqtSignal()
    playback_finished  = pyqtSignal()
    tts_error          = pyqtSignal(str)
    position_changed   = pyqtSignal(int)   # ms
    duration_changed   = pyqtSignal(int)   # ms

    def __init__(self, model_path: str = "", parent=None):
        super().__init__(parent)
        self._model_path = model_path
        self._speed      = 1.0
        self._player: AudioPlayer | None = None
        self._synth:  _SynthesisThread | None = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_model(self, path: str):
        self._model_path = path

    def set_speed(self, speed: float):
        self._speed = max(0.5, min(2.0, speed))

    # ------------------------------------------------------------------
    # Contrôles
    # ------------------------------------------------------------------

    def speak(self, text: str):
        """Lance la synthèse (ou récupère le cache) puis la lecture."""
        self.stop()
        if not text.strip():
            return

        cache = _cache_path(text, self._speed)
        if cache.exists():
            logger.debug("Cache TTS trouvé : %s", cache)
            self._start_playback(str(cache))
        else:
            self._synthesize(text, cache)

    def pause(self):
        if self._player and self._player.isRunning():
            self._player.pause()

    def resume(self):
        if self._player and self._player.isRunning():
            self._player.resume()

    def stop(self):
        if self._synth and self._synth.isRunning():
            self._synth.terminate()
            self._synth.wait(2000)
            self._synth = None
        if self._player and self._player.isRunning():
            self._player.stop()
            self._player.wait(2000)
            self._player = None

    # ------------------------------------------------------------------
    # Internes
    # ------------------------------------------------------------------

    def _synthesize(self, text: str, output: Path):
        if not self._model_path:
            self.tts_error.emit(
                "Aucun modèle Piper configuré.\n"
                "Cliquez sur ⚙ dans la barre TTS pour sélectionner un fichier .onnx.\n\n"
                "Téléchargement : https://huggingface.co/rhasspy/piper-voices/tree/main"
            )
            return

        self.synthesis_started.emit()
        self._synth = _SynthesisThread(text, output, self._model_path, self._speed)
        self._synth.finished.connect(self._on_synth_done)
        self._synth.error.connect(self.tts_error)
        self._synth.start()

    def _on_synth_done(self, path: str):
        self.synthesis_finished.emit()
        self._start_playback(path)

    def _start_playback(self, path: str):
        self._player = AudioPlayer()
        self._player.set_file(path)
        self._player.playback_started.connect(self.playback_started)
        self._player.playback_finished.connect(self.playback_finished)
        self._player.playback_error.connect(self.tts_error)
        self._player.position_changed.connect(self.position_changed)
        self._player.duration_changed.connect(self.duration_changed)
        self._player.start()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_path(text: str, speed: float) -> Path:
    key = f"{text}|{speed:.2f}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.wav"
