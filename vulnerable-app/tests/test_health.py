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


def test_only_health_get_route_is_registered():
    app = create_app()
    rules = list(app.url_map.iter_rules())
    assert len(rules) == 1
    assert rules[0].rule == "/healthz"
    assert rules[0].methods == {"GET", "HEAD", "OPTIONS"}
    assert app.test_client().post("/healthz").status_code == 405
