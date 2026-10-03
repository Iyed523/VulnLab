"""Unit configuration checks; acceptance runs with real SQL, Redis and CSRF."""

import importlib.util
from pathlib import Path

import pytest

from vulnlab_vulnerable import create_app
from vulnlab_vulnerable.auth import local_destination
from vulnlab_vulnerable.session_backend import UnavailableSessionInterface

pytestmark = pytest.mark.preserved_protection


@pytest.mark.parametrize(
    "value",
    [
        "https://example.invalid",
        "//example.invalid",
        "\\\\example.invalid",
        "/account?next=//example.invalid",
        "/tickets",
        "/account/",
        "https://vulnerable.vulnlab.test:8443/account",
    ],
)
def test_redirect_allowlist_rejects_external_or_unapproved_paths(value):
    assert local_destination(value) is None


def test_missing_configuration_cannot_fall_back_to_client_sessions():
    app = create_app()
    assert isinstance(app.session_interface, UnavailableSessionInterface)
    assert app.test_client().get("/login").status_code == 503
    health = app.test_client().get("/healthz")
    assert health.get_json() == {"status": "ok"}
    assert "Set-Cookie" not in health.headers


def test_csrf_duration_is_accepted_by_pinned_flask_wtf():
    from flask_wtf.csrf import generate_csrf, validate_csrf

    app = create_app({"SECRET_KEY": b"fictitious-unit-key-only"})
    assert app.config["WTF_CSRF_TIME_LIMIT"] == 900
    with app.test_request_context("/login", base_url="https://vulnerable.vulnlab.test"):
        validate_csrf(generate_csrf())


def test_key_generator_preserves_existing_file(tmp_path):
    script = Path(__file__).parents[2] / "scripts/generate_session_key.py"
    spec = importlib.util.spec_from_file_location("generate_key", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "session-key"
    module.generate(path)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        module.generate(path)
    assert path.read_bytes() == original
    assert len(original.strip()) == 64


@pytest.mark.parametrize("data", [b"\xc0", b"\x90", b"\x80\x04legacy-pickle"])
def test_session_serializer_rejects_invalid_records(data):
    import msgspec

    from vulnlab_vulnerable.session_backend import StrictSerializer

    with pytest.raises(msgspec.DecodeError):
        StrictSerializer().decode(data)
