"""HTTP contracts without claiming live SQL/Redis validation."""

import pytest

from vulnlab_vulnerable import create_app


def test_every_private_view_declares_protection():
    app = create_app()
    public = {"static", "healthz", "auth.login", "auth.register"}
    for endpoint, view in app.view_functions.items():
        assert bool(getattr(view, "vulnlab_protected", False)) == (
            endpoint not in public
        )


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/account/edit"),
        ("POST", "/account/edit"),
        ("GET", "/admin/users"),
        ("POST", "/admin/users/-1001/activate"),
        ("POST", "/admin/users/-1001/deactivate"),
    ],
)
def test_new_routes_have_no_backend_fallback(method, path):
    response = create_app().test_client().open(path, method=method)
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"


def test_admin_status_is_post_only():
    client = create_app().test_client()
    for action in ("activate", "deactivate"):
        assert client.get(f"/admin/users/-1001/{action}").status_code == 405
