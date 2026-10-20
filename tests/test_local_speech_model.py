from hashlib import sha256

import pytest

import app.integrations.local_speech_model as catalog_module
from app.integrations.local_speech_model import LocalSpeechModelCatalog, ModelFile, git_blob_sha1


def test_confirmed_model_pull_is_fixed_revision_atomic_and_digest_checked(tmp_path, monkeypatch):
    config = b'{"model": "test"}'
    weights = b"local model test bytes"
    files = (ModelFile("config.json", len(config), git_blob_sha1(config)),
             ModelFile("model.bin", len(weights), git_blob_sha1(weights), sha256(weights).hexdigest()))
    monkeypatch.setattr(catalog_module, "TINY_FILES", files)
    data = {"config.json": config, "model.bin": weights}
    calls = []
    catalog = LocalSpeechModelCatalog(tmp_path / "models", downloader=lambda item: calls.append(item.name) or data[item.name])
    preview = catalog.preview()
    assert preview["state"] == "not-installed"
    assert preview["model_id"] == "Systran/faster-whisper-tiny"
    assert preview["revision"] == catalog_module.MODEL_REVISION
    with pytest.raises(ValueError, match="Review"):
        catalog.install(confirmed=False, manifest_digest=preview["manifest_digest"])
    assert calls == []
    result = catalog.install(confirmed=True, manifest_digest=preview["manifest_digest"])
    assert result["state"] == "installed" and not result["already_installed"]
    assert calls == ["config.json", "model.bin"]
    assert (tmp_path / "models" / "faster-whisper-tiny" / "model.bin").read_bytes() == weights
    assert catalog.preview()["state"] == "installed"


def test_bad_model_digest_leaves_no_partial_model(tmp_path, monkeypatch):
    expected = b"expected"
    spec = ModelFile("model.bin", len(expected), "0" * 40, "0" * 64)
    monkeypatch.setattr(catalog_module, "TINY_FILES", (spec,))
    catalog = LocalSpeechModelCatalog(tmp_path / "models", downloader=lambda _item: expected)
    preview = catalog.preview()
    with pytest.raises(RuntimeError, match="digest"):
        catalog.install(confirmed=True, manifest_digest=preview["manifest_digest"])
    assert not (tmp_path / "models" / "faster-whisper-tiny").exists()


def test_model_url_redirects_are_https_and_restricted_to_known_huggingface_hosts():
    from app.integrations.local_speech_model import _host, _SafeModelRedirects
    assert _host("https://huggingface.co/repository") == "huggingface.co"
    assert _host("http://huggingface.co/model") == ""
    assert _host("https://user:password@huggingface.co/model") == ""
    redirect = _SafeModelRedirects()
    request = __import__("urllib.request").request.Request("https://huggingface.co/model")
    assert redirect.redirect_request(request, None, 302, "Found", {}, "https://evil.example/model") is None
    assert redirect.redirect_request(request, None, 302, "Found", {}, "http://cdn-lfs.huggingface.co/model") is None


def test_local_speech_runtime_can_refresh_after_owner_installs_the_optional_pack(tmp_path, monkeypatch):
    from app.integrations import local_speech
    monkeypatch.setattr(local_speech.importlib.util, "find_spec", lambda _name: object())
    provider = local_speech.FasterWhisperLocalProvider(tmp_path, runtime_available=None)
    assert provider.status().runtime == "available"
    monkeypatch.setattr(local_speech.importlib.util, "find_spec", lambda _name: None)
    assert provider.refresh_runtime().runtime == "unavailable"
    fixed = local_speech.FasterWhisperLocalProvider(tmp_path, runtime_available=False)
    monkeypatch.setattr(local_speech.importlib.util, "find_spec", lambda _name: object())
    assert fixed.refresh_runtime().runtime == "unavailable"
