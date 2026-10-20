"""Owner-confirmed, isolated Windows wheels for optional local media features.

Package bytes are never fetched from this module until an owner confirms the
preview manifest through the protected capability-pack API.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from threading import Lock

from app.knowledge.faiss_pack import OptionalFaissPack, WheelSpec, application_data_root


def _wheel(filename: str, url: str, size: int, digest: str) -> WheelSpec:
    return WheelSpec(filename, url, size, digest)


EYES_WHEELS = (
    _wheel("pillow-13.0.0-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/50/e2/7ad17747517e4c813dca78257d6bb593466f8231baf1384bc98d92745edb/pillow-13.0.0-cp314-cp314-win_amd64.whl", 7_281_830, "f7cbb7a64e7ec664775195e4f81923bc8a93d9451b963f844e59118f63147a7a"),
    _wheel("mss-10.2.0-py3-none-any.whl", "https://files.pythonhosted.org/packages/f2/c3/313e14f245c79b4c05bd0f3a84a4813aa26fa10f8993aebd91d04c5fad3f/mss-10.2.0-py3-none-any.whl", 67_106, "e79f428899280e7e64e38365b5bfed683851ebea807eeaeadaf06eb8e0d67197"),
    _wheel("opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl", "https://files.pythonhosted.org/packages/b8/88/763b967f7efd7226b82c9fae16d560cba049b1f0c036647e65c610fd636e/opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl", 43_825_962, "829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e"),
    _wheel("numpy-2.5.4-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/52/9a/e1e512ebc948d5b9dd33b08736760f0ebbed2848fd4eda1f553088a6dcee/numpy-2.5.4-cp314-cp314-win_amd64.whl", 12_703_552, "2ca144f15135b6212a5c47b1e2aeca6e412f102f95a2d5d88d8aec77eb255de3"),
    _wheel("pytesseract-0.3.13-py3-none-any.whl", "https://files.pythonhosted.org/packages/7a/33/8312d7ce74670c9d39a532b2c246a853861120486be9443eebf048043637/pytesseract-0.3.13-py3-none-any.whl", 14_705, "7a99c6c2ac598360693d83a416e36e0b33a67638bb9d77fdcac094a3589d4b34"),
)

EARS_WHEELS = (
    _wheel("faster_whisper-1.2.1-py3-none-any.whl", "https://files.pythonhosted.org/packages/05/99/49ee85903dee060d9f08297b4a342e5e0bcfca2f027a07b4ee0a38ab13f9/faster_whisper-1.2.1-py3-none-any.whl", 1_118_909, "79a66ad50688c0b794dd501dc340a736992a6342f7f95e5811be60b5224a26a7"),
    _wheel("huggingface_hub-2.2.0-py3-none-any.whl", "https://files.pythonhosted.org/packages/eb/b0/0f7b430fd100b3a3b037fdbb314878200241082e607b3383c63d91a13a72/huggingface_hub-2.2.0-py3-none-any.whl", 839_884, "1667f145dc56dc210d60966069397df9ecfca9607a5d43db88b308c89dae56b3"),
    _wheel("hf_xet-1.7.0-cp38-abi3-win_amd64.whl", "https://files.pythonhosted.org/packages/4d/59/b35106dfa71b6eef605dc88bd038fe99c7f86fb132a15b60d0bf2f235b2c/hf_xet-1.7.0-cp38-abi3-win_amd64.whl", 3_822_644, "2b7bb5727889b0f2436dbaaad8fc4c3e66b8240d992716989e0c086b4278b1bc"),
    _wheel("ctranslate2-4.8.3-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/15/99/7c3e8d0b8527acc4ed18ddc97f96d70928a672faba37d60cea1fe7bc831e/ctranslate2-4.8.3-cp314-cp314-win_amd64.whl", 19_485_275, "03b0ad8c6325f142341a7a7431b5ab693b51f43918be1c116b80ebb6e3c1f85e"),
    _wheel("onnxruntime-1.31.0-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/6a/66/0bf4fdb9f58efa69cf4eddde24c72aebcc628d6ff1d67c9546145c6b9922/onnxruntime-1.31.0-cp314-cp314-win_amd64.whl", 15_268_709, "83e3dbcf6abc6189c4bdf7d329c07ba1133c88172134c266d84b4409aa3b9dbf"),
    _wheel("av-19.0.1-cp312-abi3-win_amd64.whl", "https://files.pythonhosted.org/packages/e6/dc/a87a5a5e3ac462734f9befd8bad1447301e5802d8c111e22bf708fba7af3/av-19.0.1-cp312-abi3-win_amd64.whl", 28_149_519, "906fc3db09288319a75ea23ffefb59961c7dbe0d1c074601507a89de7d8593d8"),
    _wheel("tokenizers-0.23.3-cp310-abi3-win_amd64.whl", "https://files.pythonhosted.org/packages/d1/6c/24f074c9a0efb98e61b20aafe6b2641922d5db24e447d5d6daffd9e17555/tokenizers-0.23.3-cp310-abi3-win_amd64.whl", 2_872_101, "1f0823bb00c5fdc98e487354d54dd55a03848d61a1a0bf29a68c77f24f3b26c3"),
    _wheel("tqdm-4.70.1-py3-none-any.whl", "https://files.pythonhosted.org/packages/a7/03/921a3d3c75785aca9ebfbfcabfbc3a1be12e2ab5265deb026d55a5a3f83e/tqdm-4.70.1-py3-none-any.whl", 80_199, "c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73"),
    _wheel("numpy-2.5.4-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/52/9a/e1e512ebc948d5b9dd33b08736760f0ebbed2848fd4eda1f553088a6dcee/numpy-2.5.4-cp314-cp314-win_amd64.whl", 12_703_552, "2ca144f15135b6212a5c47b1e2aeca6e412f102f95a2d5d88d8aec77eb255de3"),
    _wheel("pyyaml-6.0.3-cp314-cp314-win_amd64.whl", "https://files.pythonhosted.org/packages/23/20/bb6982b26a40bb43951265ba29d4c246ef0ff59c9fdcdf0ed04e0687de4d/pyyaml-6.0.3-cp314-cp314-win_amd64.whl", 156_429, "4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac"),
    _wheel("flatbuffers-25.12.19-py2.py3-none-any.whl", "https://files.pythonhosted.org/packages/e8/2d/d2a548598be01649e2d46231d151a6c56d10b964d94043a335ae56ea2d92/flatbuffers-25.12.19-py2.py3-none-any.whl", 26_661, "7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4"),
    _wheel("protobuf-7.36.2-py3-none-any.whl", "https://files.pythonhosted.org/packages/e4/04/d52c7016b04b6c5108f26691f9d33ec82a9b65d041f1a9c771137693d618/protobuf-7.36.2-py3-none-any.whl", 179_806, "bdb3a345d48db958e6ce1f18e508beb0cc981d64f24088427549c866cd039f1e"),
    _wheel("filelock-4.2.4-py3-none-any.whl", "https://files.pythonhosted.org/packages/e0/1b/5e74289a1878e666bb4b65fe5805a04cafcac2aa5f519ef1ead67ef91c56/filelock-4.2.4-py3-none-any.whl", 162_475, "301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e"),
    _wheel("fsspec-2026.9.0-py3-none-any.whl", "https://files.pythonhosted.org/packages/6c/c0/a98505f18594f1bce828bb159cec0fcf9860562f1a2c85913409fc8f3d9e/fsspec-2026.9.0-py3-none-any.whl", 221_738, "8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f"),
    _wheel("colorama-0.4.6-py2.py3-none-any.whl", "https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6-py2.py3-none-any.whl", 25_335, "4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6"),
    _wheel("packaging-26.3-py3-none-any.whl", "https://files.pythonhosted.org/packages/63/34/ba1c580383c9eada3711951fef0795c80b829a078d72188184bcab9dd527/packaging-26.3-py3-none-any.whl", 129_956, "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"),
    _wheel("sounddevice-0.5.6-py3-none-win_amd64.whl", "https://files.pythonhosted.org/packages/8d/3e/cbc593c31a5f0d817b3fe97e64aa8461bd0f55cb07b67ce1b776296ae336/sounddevice-0.5.6-py3-none-win_amd64.whl", 1_009_630, "7f4162f514f007b0bf25a3ccfed3f1705bc2ec311888a90232729eec4f57a4f4"),
)

VOICE_WHEELS = (
    _wheel("pyttsx3-2.99-py3-none-any.whl", "https://files.pythonhosted.org/packages/84/14/9fb5842581f0419b5eb85f8c26c1c0c0f4cf6b4d5be638ae3157316a2650/pyttsx3-2.99-py3-none-any.whl", 32_157, "ff3e4ff756c24d72b9f3f2f304e0edaafd0f58adb0e6f4b90d930440cda8b207"),
    _wheel("comtypes-1.4.17-py3-none-any.whl", "https://files.pythonhosted.org/packages/89/9c/d0bc1fb69ad22a04bdc01dd9b5613a2ebc4d02ba1ec24b02127dc93791ba/comtypes-1.4.17-py3-none-any.whl", 298_743, "4e0a221dde2c589b82977bed802efd71cd5eb67a380347b732e02735e597f586"),
)


@dataclass(frozen=True)
class PackDefinition:
    pack_id: str
    title: str
    wheels: tuple[WheelSpec, ...]
    modules: tuple[str, ...]
    source: str = "Official PyPI; exact wheel files, versions, sizes and SHA-256 pinned in this app"


PACKS = {
    "eyes": PackDefinition("eyes", "Eyes: image and OCR libraries", EYES_WHEELS,
                            ("PIL", "mss", "cv2", "pytesseract", "numpy")),
    "ears": PackDefinition("ears", "Ears: local audio and transcription runtime", EARS_WHEELS,
                            ("faster_whisper", "ctranslate2", "av", "tokenizers", "sounddevice", "numpy")),
    "voice": PackDefinition("voice", "Voice: offline Windows speech output", VOICE_WHEELS,
                             ("pyttsx3", "comtypes", "win32com.client")),
}

MAX_PACK_DOWNLOAD_BYTES = 120 * 1024 * 1024


class OptionalMediaPacks:
    """Pinned optional packs; importing this manager never downloads or installs."""

    def __init__(self, data_root: str | Path | None = None, *, downloader=None,
                 runtime_supported=None, self_tester=None):
        self._root = Path(data_root or application_data_root()).expanduser().absolute() / "capability-packs"
        self._downloader = downloader or OptionalFaissPack._download
        self._runtime_supported = runtime_supported or self._supports_this_runtime
        self._self_tester = self_tester or self._test_pack
        self._lock = Lock()
        self._working: set[str] = set()
        for pack_id in PACKS:
            if self._installed(pack_id):
                try:
                    activate_isolated_pack(self._pack_root(pack_id) / "site-packages")
                except Exception:
                    # The owner can inspect and retry the pack from Settings; startup never downloads or repairs it.
                    pass

    @staticmethod
    def _supports_this_runtime():
        return (sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 14)
                and sys.platform == "win32" and platform.machine().casefold() in {"amd64", "x86_64"})

    def _pack_root(self, pack_id: str) -> Path:
        if pack_id not in PACKS:
            raise ValueError("Choose a supported local capability pack")
        return self._root / pack_id

    def _installed(self, pack_id: str) -> bool:
        root = self._pack_root(pack_id)
        site = root / "site-packages"
        try:
            return (root.is_dir() and site.is_dir() and not root.is_symlink()
                    and not self._root.is_symlink() and root.resolve(strict=True) == root
                    and site.resolve(strict=True) == site
                    and (root / "manifest.json").is_file() and not (root / "manifest.json").is_symlink()
                    and json.loads((root / "manifest.json").read_text(encoding="utf-8")).get("manifest_digest")
                    == self._manifest_digest(PACKS[pack_id]))
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    @staticmethod
    def _manifest_digest(definition: PackDefinition) -> str:
        payload = [{"filename": item.filename, "url": item.url, "size": item.size,
                    "sha256": item.sha256} for item in definition.wheels]
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def preview(self, pack_id: str | None = None) -> dict:
        if pack_id is None:
            return {"items": [self.preview(identifier) for identifier in PACKS]}
        definition = PACKS.get(pack_id)
        if definition is None:
            raise ValueError("Choose a supported local capability pack")
        installed = self._installed(pack_id)
        return {
            "pack_id": pack_id, "title": definition.title,
            "state": "working" if pack_id in self._working else "installed" if installed else "not-installed",
            "supported": bool(self._runtime_supported()),
            "version": ", ".join(Path(item.filename).stem.rsplit("-", 1)[0] for item in definition.wheels),
            "files": [item.filename for item in definition.wheels],
            "download_bytes": sum(item.size for item in definition.wheels),
            "manifest_digest": self._manifest_digest(definition), "source": definition.source,
            "compatibility": "CPython 3.14, Windows x64 only; no source distributions or dependency resolution",
            "install_action": "Owner confirmation required; verified wheels install into an isolated app-local directory.",
            "detail": "Run the local self-test before use. Tesseract engine/language data and speech models are separate.",
        }

    def install(self, pack_id: str, *, confirmed: bool, manifest_digest: str) -> dict:
        with self._lock:
            return self._install(pack_id, confirmed=confirmed, manifest_digest=manifest_digest)

    def _install(self, pack_id: str, *, confirmed: bool, manifest_digest: str) -> dict:
        definition = PACKS.get(pack_id)
        if definition is None:
            raise ValueError("Choose a supported local capability pack")
        preview = self.preview(pack_id)
        if not preview["supported"]:
            raise RuntimeError("These pinned wheels support CPython 3.14 on Windows x64 only")
        if self._installed(pack_id):
            return {"pack_id": pack_id, "state": "installed", "already_installed": True}
        if confirmed is not True or manifest_digest != preview["manifest_digest"]:
            raise ValueError("Review the current pinned wheel versions, total size, and digest, then explicitly confirm installation")
        total = sum(item.size for item in definition.wheels)
        if total > MAX_PACK_DOWNLOAD_BYTES:
            raise RuntimeError("The selected optional pack exceeds its download limit")
        self._root.mkdir(parents=True, exist_ok=True)
        if self._root.is_symlink() or self._root.resolve() != self._root:
            raise RuntimeError("Optional pack storage is not a safe local directory")
        root = self._pack_root(pack_id)
        stage = Path(tempfile.mkdtemp(prefix=f".{pack_id}-stage-", dir=self._root))
        activated = False
        published = False
        try:
            site = stage / "site-packages"
            site.mkdir()
            for spec in definition.wheels:
                data = self._downloader(spec)
                if not isinstance(data, bytes) or len(data) != spec.size or sha256(data).hexdigest() != spec.sha256:
                    raise RuntimeError("A pinned optional wheel failed its size or SHA-256 check")
                OptionalFaissPack._extract_wheel(data, spec, site)
            (stage / "manifest.json").write_text(json.dumps({
                "pack_id": pack_id, "manifest_digest": preview["manifest_digest"],
                "source": definition.source,
            }, sort_keys=True), encoding="utf-8")
            if root.exists() or root.is_symlink():
                raise RuntimeError("Optional pack storage already exists; inspect it before retrying")
            stage.rename(root)
            published = True
            activate_isolated_pack(root / "site-packages")
            activated = True
            return {"pack_id": pack_id, "state": "installed", "already_installed": False}
        except Exception:
            if published and not activated and root.exists() and root.parent == self._root:
                shutil.rmtree(root, ignore_errors=True)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)

    def self_test(self, pack_id: str) -> dict:
        if pack_id not in PACKS:
            raise ValueError("Choose a supported local capability pack")
        if not self._installed(pack_id):
            return {"pack_id": pack_id, "state": "not-installed", "detail": "Install this optional pack after reviewing its pinned wheels."}
        try:
            result = self._self_tester(pack_id)
            if result.get("state") == "working":
                self._working.add(pack_id)
            else:
                self._working.discard(pack_id)
            return {"pack_id": pack_id, **result}
        except Exception:
            self._working.discard(pack_id)
            return {"pack_id": pack_id, "state": "failed", "detail": "Local capability self-test failed; inspect the configured OCR engine, model, or device."}

    def mark_working(self, pack_id: str) -> None:
        if pack_id not in PACKS or not self._installed(pack_id):
            return
        self._working.add(pack_id)

    @staticmethod
    def _test_pack(pack_id: str) -> dict:
        modules = PACKS[pack_id].modules
        for name in modules:
            try:
                if importlib.util.find_spec(name) is None:
                    raise ImportError
                importlib.import_module(name)
            except Exception:
                return {"state": "failed", "detail": f"Required local module is unavailable: {name}. Reinstall this pinned pack."}
        if pack_id == "eyes":
            try:
                import pytesseract
                Image = importlib.import_module("PIL.Image")
                ImageDraw = importlib.import_module("PIL.ImageDraw")
                image = Image.new("RGB", (600, 120), "white")
                ImageDraw.Draw(image).text((20, 20), "ERSELMETZ 123", fill="black",
                                           font=Image.load_default(size=54))
                text = pytesseract.image_to_string(image, timeout=2.0)
                image.close()
                if "ERSELMETZ" not in text.upper():
                    return {"state": "failed", "detail": "Local OCR returned no expected text from its temporary self-test image."}
            except Exception:
                return {"state": "installed", "detail": "Image libraries loaded. Install Tesseract and language data separately, then configure its executable path before OCR can be tested."}
            return {"state": "working", "detail": "Image libraries and local OCR recognized the expected text in a temporary synthetic image."}
        if pack_id == "ears":
            import sounddevice
            try:
                device = sounddevice.default.device
                if device is None or device[0] is None:
                    raise RuntimeError
                sounddevice.query_devices(device[0], "input")
            except Exception:
                return {"state": "installed", "detail": "Local speech runtime loaded, but no default microphone input could be checked. Start a five-second push-to-talk test from Chat."}
            return {"state": "installed", "detail": "Local speech runtime and microphone device are present. Record a five-second push-to-talk test from Chat to verify transcription; no audio was captured by this check."}
        return {"state": "installed", "detail": "Offline speech libraries loaded. Use Chat's local voice test to verify playback and Stop on this device."}


def activate_isolated_pack(site_packages: str | Path) -> None:
    path = Path(site_packages).resolve(strict=True)
    if not path.is_dir() or path.name != "site-packages":
        raise RuntimeError("Capability pack location is invalid")
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        handles = getattr(activate_isolated_pack, "_dll_handles", [])
        for directory in path.iterdir():
            if directory.is_dir() and directory.name.endswith(".libs"):
                handles.append(os.add_dll_directory(str(directory)))
        activate_isolated_pack._dll_handles = handles
