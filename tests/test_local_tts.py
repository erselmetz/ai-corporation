import threading
import time

from app.integrations.local_tts import LocalPyttsx3Output


class FakeEngine:
    def __init__(self, *, finishes=True):
        self.finishes = finishes
        self.busy = False
        self.spoken = []
        self.stopped = False

    def say(self, text): self.spoken.append(text); self.busy = True
    def startLoop(self, _use_driver_loop): pass
    def isBusy(self): return self.busy
    def iterate(self):
        if self.finishes: self.busy = False
    def stop(self): self.busy = False; self.stopped = True


def test_local_voice_self_test_speaks_only_fixed_local_text_and_reports_completion():
    engine = FakeEngine()
    output = LocalPyttsx3Output(engine_factory=lambda: engine)
    initial = output.start_test()
    assert initial["active"] is True
    for _ in range(50):
        if output.snapshot()["state"] == "working": break
        time.sleep(0.005)
    result = output.snapshot()
    assert result["state"] == "working" and result["active"] is False
    assert engine.spoken == [output.TEST_LINE]
    assert result["destination"] == "local Windows speech engine"
    assert result["text_retained"] is False


def test_one_click_stop_cancels_inflight_local_playback():
    engine = FakeEngine(finishes=False)
    output = LocalPyttsx3Output(engine_factory=lambda: engine, sleeper=lambda _seconds: time.sleep(0.002))
    output.start_test()
    for _ in range(50):
        if output.snapshot()["state"] == "speaking": break
        time.sleep(0.002)
    assert output.snapshot()["active"] is True
    assert output.stop()["state"] == "stopping"
    for _ in range(50):
        if output.snapshot()["state"] == "stopped": break
        time.sleep(0.002)
    assert output.snapshot()["state"] == "stopped"
    assert engine.stopped


def test_output_failure_does_not_leak_exception_details_or_claim_working():
    def fail(): raise RuntimeError("C:\\sensitive\\profile\\device.dll secret")
    output = LocalPyttsx3Output(engine_factory=fail)
    output.start_test()
    for _ in range(50):
        result = output.snapshot()
        if result["state"] == "failed": break
        time.sleep(0.002)
    assert result["state"] == "failed"
    assert "sensitive" not in result["detail"] and "secret" not in result["detail"]
