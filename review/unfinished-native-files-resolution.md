# Resolution of five preserved native prototype files

28 October 2026. Inspected against local checkpoint
`aaa3e00648fa58c6e63a47eb3178b028dd837442` (`task-227-no-node`).
This is a scoped source cleanup, not a new roadmap phase or packaged release.

The five pending paths were an unfinished Tkinter Brain/intake implementation
from before the PySide6 migration. The actual entry point already delegates to
`app.qt_desktop.__main__`; none of this Tk implementation is used by the current
application. Its useful behavior is already implemented and covered in Qt.

| Pending path | Resolution and active replacement |
| --- | --- |
| `app/native_desktop/session.py` | Archived the pending version, then removed its 38 duplicate helper lines by restoring the committed file. The shared session remains intact. `qt_desktop/transport.py` owns window-scoped feed jobs, cancellation, file identity checks and note ingestion. |
| `app/native_desktop/shell.py` | Archived and removed the obsolete Tk shell. Qt `shell.py` supplies the three-pane shell, file/folder/text previews, explicit Save, cancellation, anchored inspection, revision-bound forgetting and retrieval highlights. |
| `app/native_desktop/brain_view.py` | Archived the untracked Tk widget. Qt `brain.py` supplies the shared Brain widget, anchored card, list fallback, real-data grouping and full-window/back behavior. |
| `app/native_desktop/drop.py` | Archived the untracked Windows/Tk hook. Qt drag/drop and clipboard events plus `qt_desktop/intake.py` handle explicit selections with bounds and link/secret/junk filtering. |
| `tools/native_brain_check.py` | Archived the untracked Tk-only check. Existing `qt_brain_check.py`, `qt_shell_check.py` and Qt/backend regressions cover the supported path. The old check also wrote into the retired `desktop` directory. |

The tracked `tools/native_shell_check.py` was also removed because it was the only
remaining executable consumer of the removed Tk shell and wrote into `desktop`.
No supported launcher, Qt widget, application service, permission boundary or
historical benchmark was removed. The compatibility entry point and active
`NativeSession` remain supported.

Before changing anything, all six exact files were copied and SHA-256 verified at
`D:/source/AI/ai-corporation-legacy-artifacts/unfinished-tk-20261028`.
Its `manifest.json` records each original hash. This preserves the original work
without keeping an unused parallel UI or weaker duplicate ingestion path active.

Validation:

```text
.venv/Scripts/python.exe -m pytest tests/test_qt_brain.py tests/test_native_brain.py tests/test_native_session_security.py tests/test_qt_dead_controls.py -q
24 passed, 3 warnings in 20.52s
```

These checks exercise real Qt widgets with deterministic backend boundaries:
drop preview/consent, Unicode file cancellation, anchored forget confirmation,
shared full-window Brain, bounded intake, replacement/restart, cancel/rollback,
expiry, derived-cache deletion, session security and native control actions.
The warnings concern existing Starlette/Qt deprecations. An initial command
referenced a nonexistent `test_qt_intake.py`; it collected no tests and was
corrected to the actual existing suites above. Logs remain under
`task227-review/unfinished-tk-focused*.log`.

Runtime-source searches found no remaining imports or callers of the retired
Tk modules/helper. Diff integrity passed. No new live model call, physical device
test, installer rebuild, commit, tag, push or deployment was performed for this
cleanup. Existing Task 227 artifact evidence applies to that artifact's original
commit, not a newly rebuilt cleanup artifact.
