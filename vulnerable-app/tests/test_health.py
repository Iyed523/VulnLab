"""Contrat HTTP technique, sans vérification PostgreSQL ou Redis."""

from vulnlab_vulnerable import create_app


def test_health_contract():
    app = create_app()
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}
    assert not app.debug
    assert not app.testing
    assert "Set-Cookie" not in response.headers


def test_unknown_route_has_no_diagnostics():
    response = create_app().test_client().get("/missing")
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    for diagnostic in (
        "Traceback",
        "Debugger",
        "SECRET",
        "vulnlab_vulnerable",
        "File ",
    ):
        assert diagnostic not in body


def test_health_and_m6_routes_are_registered_with_expected_methods():
    app = create_app()
    rules = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
    assert set(rules) == {
        "/healthz",
        "/register",
        "/login",
        "/logout",
        "/account",
        "/static/<path:filename>",
        "/tickets",
        "/tickets/new",
        "/tickets/<int(signed=True):ticket_id>",
        "/tickets/<int(signed=True):ticket_id>/edit",
        "/tickets/<int(signed=True):ticket_id>/delete",
        "/tickets/<int(signed=True):ticket_id>/comments",
    }
    assert rules["/healthz"] == {"GET", "HEAD", "OPTIONS"}
    assert rules["/logout"] == {"POST", "OPTIONS"}
    assert rules["/tickets/<int(signed=True):ticket_id>/delete"] == {"POST", "OPTIONS"}
    assert rules["/tickets/<int(signed=True):ticket_id>/comments"] == {
        "POST",
        "OPTIONS",
    }
    assert app.test_client().post("/healthz").status_code == 405
