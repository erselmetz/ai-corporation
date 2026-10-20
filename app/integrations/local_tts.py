"""Explicit, bounded pyttsx3 test playback with a process-local Stop latch."""
from __future__ import annotations

import threading
import time


class LocalPyttsx3Output:
    TEST_LINE = "ERSELMETZ AI local voice test. Press Stop at any time."
    MAX_TEST_SECONDS = 12

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
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.snapshot()
            cancel = threading.Event()
            self._cancel = cancel
            self._state = "starting"
            self._detail = "Starting an explicit local speech self-test."
            self._thread = threading.Thread(target=self._run, args=(cancel,),
                                            name="local-pyttsx3-test", daemon=True)
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

    def _run(self, cancel: threading.Event) -> None:
        engine = None
        started = self._clock()
        try:
            engine = self._engine_factory()
            with self._lock:
                if cancel.is_set():
                    self._state = "stopped"
                    self._detail = "Local speech test stopped before playback."
                    return
                self._state = "speaking"
                self._detail = "Speaking a fixed local test sentence. The Stop control is active."
            engine.say(self.TEST_LINE)
            engine.startLoop(False)
            while not cancel.is_set() and engine.isBusy() and self._clock() - started < self.MAX_TEST_SECONDS:
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
                    self._detail = "Local speech test was stopped."
                elif self._clock() - started >= self.MAX_TEST_SECONDS and engine.isBusy():
                    self._state = "failed"
                    self._detail = "Local speech test exceeded its time limit."
                else:
                    self._state = "working"
                    self._detail = "The local Windows speech engine completed its test sentence."
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
