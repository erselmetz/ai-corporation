from pathlib import Path
import os

from tools.build_native import controlled_build_environment


PACKAGED_UI_DRIVERS = (
    "smoke_native.py",
    "packaged_python_journey.py",
    "packaged_chat_check.py",
    "packaged_restore_check.py",
    "packaged_browser_check.py",
)


def test_native_build_path_excludes_unrelated_tool_and_dll_directories(monkeypatch):
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join([
            r"C:\Users\owner\.cache\codex-runtimes\poppler\Library\bin",
            r"C:\Program Files\UnrelatedQt\bin",
        ]),
    )

    entries = controlled_build_environment()["PATH"].split(os.pathsep)

    assert all("codex-runtimes" not in entry.casefold() for entry in entries)
    assert all("unrelatedqt" not in entry.casefold() for entry in entries)
    assert str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32").casefold() \
        in {entry.casefold() for entry in entries}


def test_packaged_ui_drivers_follow_the_voice_first_composer_accessible_name():
    tools = Path(__file__).resolve().parents[1] / "tools"

    for name in PACKAGED_UI_DRIVERS:
        source = (tools / name).read_text(encoding="utf-8")
        assert "Optional text message" in source, name
        assert "control('Message'" not in source, name


def test_reinstall_smoke_discovers_the_current_numbered_uninstaller():
    source = (Path(__file__).resolve().parents[1] / "tools" / "python_installer_smoke.py").read_text(encoding="utf-8")

    assert "target.glob('unins*.exe')" in source
    assert "target/'unins000.exe'" not in source
