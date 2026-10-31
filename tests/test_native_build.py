from pathlib import Path
import os

from tools.build_native import controlled_build_environment


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
