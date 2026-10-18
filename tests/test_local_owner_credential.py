import sys

import pytest

from app.local_owner_credential import LocalOwnerCredentialStore, OwnerCredentialError
from app.local_owner_secret import LocalOwnerSecretError, LocalOwnerSecretStore


PASSWORD = "owner-password-for-tests"


def _protection_pair():
    marker = b"test-protected:"
    def protect(data):
        return marker + data
    def unprotect(data):
        if not data.startswith(marker):
            raise ValueError("invalid protected data")
        return data[len(marker):]
    return protect, unprotect


def test_owner_setup_persists_only_protected_verifier_and_verifies_across_store_instances(tmp_path):
    path = tmp_path / "owner.dpapi"
    protect, unprotect = _protection_pair()
    store = LocalOwnerCredentialStore(path, protect=protect, unprotect=unprotect)
    store.create(PASSWORD, PASSWORD)
    contents = path.read_bytes()
    assert PASSWORD.encode() not in contents
    assert contents.startswith(b"test-protected:")
    reopened = LocalOwnerCredentialStore(path, protect=protect, unprotect=unprotect)
    assert reopened.verify(PASSWORD) is True
    assert reopened.verify("different-owner-password") is False
    with pytest.raises(OwnerCredentialError, match="already exists"):
        reopened.create(PASSWORD, PASSWORD)


def test_owner_setup_rejects_mismatch_and_weak_password_without_writing(tmp_path):
    protect, unprotect = _protection_pair()
    path = tmp_path / "owner.dpapi"
    store = LocalOwnerCredentialStore(path, protect=protect, unprotect=unprotect)
    with pytest.raises(OwnerCredentialError, match="12 to 1024"):
        store.create("short", "short")
    with pytest.raises(OwnerCredentialError, match="do not match"):
        store.create(PASSWORD, PASSWORD + "different")
    assert not path.exists()


def test_corrupt_saved_owner_verifier_fails_closed(tmp_path):
    protect, unprotect = _protection_pair()
    path = tmp_path / "owner.dpapi"
    path.write_bytes(b"corrupt")
    store = LocalOwnerCredentialStore(path, protect=protect, unprotect=unprotect)
    with pytest.raises(OwnerCredentialError, match="unavailable or unreadable"):
        store.verify(PASSWORD)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI integration")
def test_current_user_dpapi_protects_and_reloads_owner_verifier(tmp_path):
    path = tmp_path / "owner.dpapi"
    store = LocalOwnerCredentialStore(path)
    store.create(PASSWORD, PASSWORD)
    assert PASSWORD.encode() not in path.read_bytes()
    assert store.verify(PASSWORD) is True
    assert store.verify("different-owner-password") is False


def test_owner_secret_store_opt_in_round_trips_without_plaintext_and_can_be_cleared(tmp_path):
    path = tmp_path / "gemini.dpapi"
    marker = b"test-protected:"
    key = b"deterministic-test-mask"

    def protect(data):
        return marker + bytes(value ^ key[index % len(key)] for index, value in enumerate(data))

    def unprotect(data):
        if not data.startswith(marker):
            raise ValueError("invalid protected data")
        payload = data[len(marker):]
        return bytes(value ^ key[index % len(key)] for index, value in enumerate(payload))

    store = LocalOwnerSecretStore(path, protect=protect, unprotect=unprotect)
    secret = "AIza" + "B" * 35
    store.save(secret)
    assert path.read_bytes().startswith(marker)
    assert secret.encode() not in path.read_bytes()
    reopened = LocalOwnerSecretStore(path, protect=protect, unprotect=unprotect)
    assert reopened.load() == secret
    reopened.clear()
    assert reopened.load() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI integration")
def test_current_user_dpapi_protects_and_reloads_opted_in_gemini_credential(tmp_path):
    path = tmp_path / "gemini-credential.dpapi"
    secret = "AIza" + "C" * 35
    store = LocalOwnerSecretStore(path)
    store.save(secret)
    assert secret.encode() not in path.read_bytes()
    assert LocalOwnerSecretStore(path).load() == secret
    assert LocalOwnerSecretStore(path).load() == secret
    LocalOwnerSecretStore(path).clear()
    assert LocalOwnerSecretStore(path).load() is None


def test_owner_secret_store_fails_closed_when_protection_or_saved_data_is_invalid(tmp_path):
    path = tmp_path / "gemini.dpapi"
    store = LocalOwnerSecretStore(path, protect=lambda _data: (_ for _ in ()).throw(ValueError()))
    with pytest.raises(LocalOwnerSecretError, match="could not be protected"):
        store.save("AIza" + "D" * 35)
    path.write_bytes(b"not-protected")
    with pytest.raises(LocalOwnerSecretError, match="unavailable or unreadable"):
        LocalOwnerSecretStore(path, unprotect=lambda _data: (_ for _ in ()).throw(ValueError())).load()
