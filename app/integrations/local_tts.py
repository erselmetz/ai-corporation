"""Bounded offline pyttsx3 playback with a process-local Stop latch."""
from __future__ import annotations

import threading
import time


class LocalPyttsx3Output:
    TEST_LINE = "ERSELMETZ AI local voice test. Press Stop at any time."
    MAX_TEST_SECONDS = 12
    MAX_OUTPUT_SECONDS = 120
    MAX_TEXT_CHARS = 4000

    def __init__(self, *, engine_factory=None, clock=time.monotonic, sleeper=time.sleep, on_success=None):
        self._engine_factory = engine_factory or self._default_engine
        self._clock = clock
        self._sleeper = sleeper
        self._on_success = on_success
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel: threading.Event | None = None
        self._state = "inactive"
        self._detail = "Offline speech test has not run."

    @staticmethod
    def _default_engine():
        import pyttsx3
        return pyttsx3.init()

    def snapshot(self) -> dict[str, str | bool]:
        with self._lock:
            return {"state": self._state, "active": self._state in {"starting", "speaking", "stopping"},
                    "detail": self._detail, "destination": "local Windows speech engine", "text_retained": False}

    def start_test(self) -> dict:
        return self.start_text(self.TEST_LINE, test=True)

    def start_text(self, text: str, *, test: bool = False) -> dict:
        if not isinstance(text, str):
            raise ValueError("Local speech text must be plain text")
        text = text.strip()
        if not text or len(text) > self.MAX_TEXT_CHARS:
            raise ValueError("Local speech text must contain 1 to 4000 characters")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.snapshot()
            cancel = threading.Event()
            self._cancel = cancel
            self._state = "starting"
            self._detail = "Starting offline speech playback."
            self._thread = threading.Thread(target=self._run, args=(cancel, text, test),
                                            name="local-pyttsx3-output", daemon=True)
            self._thread.start()
            return self.snapshot()

    def stop(self) -> dict:
        with self._lock:
            cancel = self._cancel
            active = self._state in {"starting", "speaking", "stopping"}
            if cancel is not None:
                cancel.set()
            if active:
                self._state = "stopping"
                self._detail = "Stop requested; local speech playback is stopping."
            return self.snapshot()

    def _run(self, cancel: threading.Event, text: str, test: bool) -> None:
        engine = None
        started = self._clock()
        deadline = self.MAX_TEST_SECONDS if test else self.MAX_OUTPUT_SECONDS
        try:
            engine = self._engine_factory()
            with self._lock:
                if cancel.is_set():
                    self._state = "stopped"
                    self._detail = "Local speech stopped before playback."
                    return
                self._state = "speaking"
                self._detail = "Speaking locally. The Stop control is active."
            engine.say(text)
            engine.startLoop(False)
            while not cancel.is_set() and engine.isBusy() and self._clock() - started < deadline:
                engine.iterate()
                self._sleeper(0.02)
            if cancel.is_set() or engine.isBusy():
                engine.stop()
            end_loop = getattr(engine, "endLoop", None)
            if callable(end_loop):
                end_loop()
            with self._lock:
                if cancel.is_set():
                    self._state = "stopped"
                    self._detail = "Local speech was stopped."
                elif self._clock() - started >= deadline and engine.isBusy():
                    self._state = "failed"
                    self._detail = "Local speech exceeded its time limit."
                else:
                    self._state = "working"
                    self._detail = ("The local Windows speech engine completed its test sentence."
                                    if test else "The local Windows speech engine completed the reply.")
                    if callable(self._on_success):
                        self._on_success()
        except Exception:
            with self._lock:
                self._state = "failed"
                self._detail = "Local speech output could not start or finish. Check installed local voices and retry."
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
