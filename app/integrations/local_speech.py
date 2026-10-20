"""Optional explicit-directory local Faster-Whisper speech adapter."""
from dataclasses import dataclass, field
import importlib.util
from io import BytesIO
from pathlib import Path
import re
import threading
import wave

from app.integrations.speech import SpeechInputRequest, SpeechTranscript


MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
MAX_MODEL_CATALOG_ITEMS = 32
MAX_MODEL_CATALOG_ENTRIES_SCANNED = 256
MAX_SEGMENTS = 1_000
RUNTIME_MODULES = ("faster_whisper", "huggingface_hub", "ctranslate2", "onnxruntime",
                   "av", "numpy", "tokenizers", "tqdm", "sounddevice")


class LocalSpeechUnavailable(RuntimeError):
    """A safe, bounded local speech availability or execution error."""


@dataclass(frozen=True)
class LocalSpeechStatus:
    runtime: str
    selected_model: str | None
    available_models: tuple[str, ...] = field(repr=False)
    state: str


def _default_model_loader(model_path: Path):
    from faster_whisper import WhisperModel
    return WhisperModel(str(model_path), device="cpu", compute_type="int8", local_files_only=True)


def _default_audio_decoder(audio: bytearray):
    import numpy
    with wave.open(BytesIO(audio), "rb") as wav:
        samples = wav.readframes(wav.getnframes())
    return numpy.frombuffer(samples, dtype=numpy.int16).astype(numpy.float32) / 32768.0


class FasterWhisperLocalProvider:
    """Loads only owner-selected, already-present models from one fixed directory."""

    backend = "local"

    def __init__(self, model_root: Path, *, model_loader=None, audio_decoder=None,
                 runtime_available: bool | None = None):
        self._root = Path(model_root).expanduser().resolve()
        self._model_loader = model_loader or _default_model_loader
        self._audio_decoder = audio_decoder or _default_audio_decoder
        self._runtime_override = runtime_available
        if runtime_available is None:
            try:
                runtime_available = all(importlib.util.find_spec(name) is not None
                                        for name in RUNTIME_MODULES)
            except (ImportError, ValueError):
                runtime_available = False
        self._runtime_available = runtime_available
        self._selected: str | None = None
        self._loaded_id: str | None = None
        self._model = None
        self._lock = threading.RLock()

    @property
    def model_root(self) -> Path:
        return self._root

    def refresh_runtime(self) -> LocalSpeechStatus:
        """Recheck imports after an owner-confirmed optional pack installation."""
        if self._runtime_override is None:
            try:
                self._runtime_available = all(importlib.util.find_spec(name) is not None
                                               for name in RUNTIME_MODULES)
            except (ImportError, ValueError):
                self._runtime_available = False
        return self.status()

    def available_models(self) -> tuple[str, ...]:
        if not self._root.is_dir():
            return ()
        result = []
        try:
            for index, child in enumerate(self._root.iterdir()):
                if index >= MAX_MODEL_CATALOG_ENTRIES_SCANNED or len(result) >= MAX_MODEL_CATALOG_ITEMS:
                    break
                if not MODEL_ID.fullmatch(child.name) or child.is_symlink() or not child.is_dir():
                    continue
                try:
                    resolved = child.resolve(strict=True)
                    if resolved.parent != self._root:
                        continue
                    model_files = (resolved / name for name in REQUIRED_MODEL_FILES)
                    if all(path.is_file() and not path.is_symlink() and path.resolve(strict=True).parent == resolved
                           for path in model_files):
                        result.append(child.name)
                except (OSError, RuntimeError):
                    continue
        except OSError:
            return ()
        return tuple(sorted(result))

    def status(self) -> LocalSpeechStatus:
        models = self.available_models()
        if not self._runtime_available:
            state = "runtime-unavailable"
        elif self._selected is None:
            state = "model-not-selected" if models else "model-unavailable"
        elif self._selected not in models:
            state = "selected-model-unavailable"
        else:
            state = "ready"
        return LocalSpeechStatus(
            runtime="available" if self._runtime_available else "unavailable",
            selected_model=self._selected,
            available_models=models,
            state=state,
        )

    def select_model(self, model_id: str) -> LocalSpeechStatus:
        if not self._runtime_available:
            raise LocalSpeechUnavailable("Optional local speech runtime is not installed")
        if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
            raise LocalSpeechUnavailable("Choose a valid local speech model identifier")
        if model_id not in self.available_models():
            raise LocalSpeechUnavailable("Selected local speech model is not available in the configured model folder")
        with self._lock:
            self._selected = model_id
            self._loaded_id = None
            self._model = None
        return self.status()

    def availability(self, *, language: str) -> str:
        if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Z0-9]{2,8})?", language):
            return "unavailable"
        return self.status().state

    def transcribe(self, request: SpeechInputRequest, *, cancelled: threading.Event) -> SpeechTranscript:
        if cancelled.is_set():
            raise LocalSpeechUnavailable("Local speech request was cancelled")
        if not self._runtime_available:
            raise LocalSpeechUnavailable("Optional local speech runtime is not installed")
        with self._lock:
            selected = self._selected
            if selected is None or selected not in self.available_models():
                raise LocalSpeechUnavailable("Select an available local speech model before transcription")
            if self._loaded_id != selected:
                try:
                    self._model = self._model_loader(self._root / selected)
                except Exception:
                    self._model = None
                    self._loaded_id = None
                    raise LocalSpeechUnavailable("Selected local speech model could not be loaded") from None
                self._loaded_id = selected
            model = self._model
        if cancelled.is_set():
            raise LocalSpeechUnavailable("Local speech request was cancelled")
        samples = None
        try:
            samples = self._audio_decoder(request.audio)
            segments, _info = model.transcribe(
                samples, language=request.language.split("-", 1)[0].lower(), beam_size=1,
                vad_filter=False, condition_on_previous_text=False)
            pieces = []
            length = 0
            for index, segment in enumerate(segments):
                if cancelled.is_set():
                    raise LocalSpeechUnavailable("Local speech request was cancelled")
                if index >= MAX_SEGMENTS:
                    raise LocalSpeechUnavailable("Local speech response exceeded its segment limit")
                value = segment.text
                if not isinstance(value, str):
                    continue
                length += len(value)
                if length > 8_192:
                    raise LocalSpeechUnavailable("Local speech response exceeded its text limit")
                pieces.append(value)
            text = "".join(pieces).strip()
            return SpeechTranscript(text=text, backend="local", language=request.language)
        except LocalSpeechUnavailable:
            raise
        except Exception:
            raise LocalSpeechUnavailable("Local speech recognition failed") from None
        finally:
            clear = getattr(samples, "fill", None)
            if callable(clear):
                clear(0)
