# Task 230 pre-implementation compatibility and frozen-pack decision

Date: 2026-10-29 (Asia/Manila). Source base: 67f07ec. Git main clean, four local commits ahead; never push/deploy. No application/build code changed before this report. Ollama is running at 127.0.0.1:11434 with installed qwen3.5:4b and nomic-embed-text; cloud stubs and retiring llama3.2 are not selected for live QA.

## Toolchain result

CPython 3.14.7, Windows AMD64, standard GIL ABI (not free-threaded). PySide6 Essentials/Addons/shiboken6 6.12.0 and PyInstaller6.22.3 are installed. Exact official PyPI release metadata exposes compatible Windows wheels for every current required native dependency and every pinned optional wheel; all optional filenames, sizes and SHA-256 values matched the official metadata. This establishes wheel/ABI availability, not successful frozen execution. Nuitka is not installed or needed; choose the already-installed PyInstaller. No Python downgrade is presently justified. If a genuine unsupported runtime appears during frozen testing, stop and offer the smallest change before switching Python.

| Package | Pinned/installed version | Compatible wheel(s) for this runtime |
|---|---|---|
| pillow | 13.0.0 | pillow-13.0.0-cp314-cp314-win_amd64.whl |
| mss | 10.2.0 | mss-10.2.0-py3-none-any.whl |
| opencv-python-headless | 5.0.0.93 | opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl |
| numpy | 2.5.4 | numpy-2.5.4-cp314-cp314-win_amd64.whl |
| pytesseract | 0.3.13 | pytesseract-0.3.13-py3-none-any.whl |
| faster-whisper | 1.2.1 | faster_whisper-1.2.1-py3-none-any.whl |
| huggingface-hub | 2.2.0 | huggingface_hub-2.2.0-py3-none-any.whl |
| hf-xet | 1.7.0 | hf_xet-1.7.0-cp38-abi3-win_amd64.whl |
| ctranslate2 | 4.8.3 | ctranslate2-4.8.3-cp314-cp314-win_amd64.whl |
| onnxruntime | 1.31.0 | onnxruntime-1.31.0-cp314-cp314-win_amd64.whl |
| av | 19.0.1 | av-19.0.1-cp312-abi3-win_amd64.whl |
| tokenizers | 0.23.3 | tokenizers-0.23.3-cp310-abi3-win_amd64.whl |
| tqdm | 4.70.1 | tqdm-4.70.1-py3-none-any.whl |
| pyyaml | 6.0.3 | pyyaml-6.0.3-cp314-cp314-win_amd64.whl |
| flatbuffers | 25.12.19 | flatbuffers-25.12.19-py2.py3-none-any.whl |
| protobuf | 7.36.2 | protobuf-7.36.2-cp310-abi3-win_amd64.whl, protobuf-7.36.2-py3-none-any.whl |
| filelock | 4.2.4 | filelock-4.2.4-py3-none-any.whl |
| fsspec | 2026.9.0 | fsspec-2026.9.0-py3-none-any.whl |
| colorama | 0.4.6 | colorama-0.4.6-py2.py3-none-any.whl |
| packaging | 26.3 | packaging-26.3-py3-none-any.whl |
| sounddevice | 0.5.6 | sounddevice-0.5.6-py3-none-any.whl, sounddevice-0.5.6-py3-none-win_amd64.whl |
| pyttsx3 | 2.99 | pyttsx3-2.99-py3-none-any.whl |
| comtypes | 1.4.17 | comtypes-1.4.17-py3-none-any.whl |
| pywinauto | 0.6.9 | pywinauto-0.6.9-py2.py3-none-any.whl |
| six | 1.17.0 | six-1.17.0-py2.py3-none-any.whl |
| faiss-cpu | 1.15.1 | faiss_cpu-1.15.1-cp314-cp314-win_amd64.whl |
| pyside6-essentials | 6.12.0 | pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl |
| pyside6-addons | 6.12.0 | pyside6_addons-6.12.0-cp310-abi3-win_amd64.whl |
| shiboken6 | 6.12.0 | shiboken6-6.12.0-cp310-abi3-win_amd64.whl |
| pyinstaller | 6.22.3 | pyinstaller-6.22.3-py3-none-win_amd64.whl |
| pywin32 | 312 | pywin32-312-cp314-cp314-win_amd64.whl |
| cffi | 2.1.1 | cffi-2.1.1-cp314-cp314-win_amd64.whl |
| cryptography | 50.0.2 | cryptography-50.0.2-cp311-abi3-win_amd64.whl, cryptography-50.0.2-cp39-abi3-win_amd64.whl |
| pydantic-core | 2.46.5 | pydantic_core-2.46.5-cp314-cp314-win_amd64.whl |
| rpds-py | 2026.6.3 | rpds_py-2026.6.3-cp314-cp314-win_amd64.whl |
| greenlet | 3.5.6 | greenlet-3.5.6-cp314-cp314-win_amd64.whl |
| psutil | 7.2.2 | psutil-7.2.2-cp37-abi3-win_amd64.whl |
| pyside6-pdf | 6.12.0.140 | pyside6_pdf-6.12.0.140-cp310-abi3-win_amd64.whl |
| pyside6-webengine | 6.12.0.140 | pyside6_webengine-6.12.0.140-cp310-abi3-win_amd64.whl |

Installed-but-unused PySide6 PDF/WebEngine distributions are not app dependencies; existing build exclusions must keep them out of the package. Pywin32 supplies win32com/win32gui; pywinauto/comtypes are the existing UI Automation path. Voice declares the old pypiwin32 metapackage, but the actual pywin32 modules are already supplied directly; do not add an obsolete duplicate wrapper. Tesseract executable/language data and speech model weights remain separate, optional prerequisites, not bundled or silently installed. Physical audio/video/output support stays Unverified.

Official release metadata with Requires-Python, wheel tags, sizes, SHA-256 and dependency metadata was saved locally in task230-review/compatibility.json. All metadata-only checks were read-only; no wheel was installed for this audit.

## Frozen optional-pack options

| Option | Size | Risk / fit |
|---|---|---|
| A. Private per-user pack folders on sys.path, exact ABI-matched wheels, app verifies SHA-256 and owner preview | Adds no optional wheel payload to base installer. Current wheel download totals below; installed expansion must be measured, not guessed | Recommended. Preserves one app Python process and existing consent. Need explicit frozen import/DLL/data tests; pin shared dependencies, never run pip/source builds or .pth scripts, and avoid treating wheel availability as runtime proof |
| B. Bundle essentials or all packs | Pillow+mss wheel archives alone are ~7 MiB; full Eyes/Ears/Voice/FAISS archives total ~172 MiB before bundler compression/overlap. Actual installed delta unmeasured | Simpler frozen imports, but larger base and license/update surface; optional features become mandatory distribution cost |
| C. Separate embedded CPython | Additional interpreter/stdlib plus the same packs; exact archive/installed size not measured because not selected | Extra process/IPC/update/signature/ABI surface; conflicts with the existing one-process direction. Reserve only for a proven blocker, with owner choice |

- eyes: 63,893,155 bytes (60.93 MiB) pinned wheel download.
- ears: 86,252,822 bytes (82.26 MiB) pinned wheel download.
- voice: 330,900 bytes (0.32 MiB) pinned wheel download.
- desktop-automation: 672,834 bytes (0.64 MiB) pinned wheel download.
- FAISS: 29,407,902 bytes (28.05 MiB) pinned wheel download.

Decision: A, reuse the existing private-pack extractor/approved-source/no-redirect/SHA-256/manifest preview. Verify Eyes inside the frozen app with a non-capturing Pillow/mss/software test. Keep Ears/Voice physical-device checks Unverified. Frozen inference/model/DLL behavior for untested packs stays Unverified even when their wheels are ABI-compatible. Do not add an embedded interpreter or change Python without a new compatibility decision.

## Existing packaging reuse and required work

Reuse one-folder/windowed PyInstaller, custom Qt plugin hook/WebEngine exclusions, inner/outer stamp equality/startup fail-closed checks, per-user data, isolated review AppId/installer, smoke window detection, metadata-only failure records, installer legacy-folder refusal, retained-data uninstall baseline, and existing owner confirmation/hash preview APIs.

Add native About/build identity, metadata-only application log, explicit optional uninstall-data choice, stronger installed-app smoke/no-listener/no-browser/no-console proof, frozen pack import/self-test, uninstall/reinstall retention journey, fresh-account/Sandbox availability evidence, unsigned/SmartScreen explanation and signing plan. Preserve old artifacts and production install/data. A review artifact must be labelled review/source-digest, never mislabelled as a clean release.

Environment limitation discovered read-only: current process is not elevated and WindowsSandbox.exe is absent. Fresh account/Sandbox verification is not yet available; an isolated current-user profile is not an equivalent claim. Continue independent packaging/installer tests and report clean-account coverage Unverified unless a genuine isolated Windows session becomes available.

## Primary sources

- [PyInstaller requirements](https://pyinstaller.org/en/stable/requirements.html) and [frozen runtime paths](https://pyinstaller.org/en/stable/runtime-information.html).
- [Qt for Python getting started](https://doc.qt.io/qtforpython-6/gettingstarted.html).
- [CTranslate2 installation](https://opennmt.net/CTranslate2/installation).
- Exact official PyPI release JSON, e.g. [PySide6 Essentials6.12.0](https://pypi.org/pypi/pyside6-essentials/6.12.0/json), [PyInstaller6.22.3](https://pypi.org/pypi/pyinstaller/6.22.3/json), [Pillow13.0.0](https://pypi.org/pypi/pillow/13.0.0/json), [CTranslate2 4.8.3](https://pypi.org/pypi/ctranslate2/4.8.3/json), [ONNX Runtime1.31.0](https://pypi.org/pypi/onnxruntime/1.31.0/json), [FAISS1.15.1](https://pypi.org/pypi/faiss-cpu/1.15.1/json). Other exact endpoints are recorded in the local metadata evidence.
