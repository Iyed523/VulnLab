"""Bounded pagination and signed routing; no database claims."""

import pytest
from werkzeug.exceptions import BadRequest

from vulnlab_vulnerable import create_app
from vulnlab_vulnerable.tickets import page_number

pytestmark = pytest.mark.preserved_protection


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=-1",
        "page=1001",
        "page=99999999",
        "page=1&page=2",
        "page=1.5",
        "page=abc",
        "page=",
        "page=%EF%BC%91",
    ],
)
def test_invalid_page_is_explicitly_rejected(query):
    with create_app().test_request_context("/tickets?" + query):
        with pytest.raises(BadRequest):
            page_number("page")


def test_negative_fixture_route_and_valid_page_bounds():
    app = create_app()
    endpoint, values = app.url_map.bind("vulnerable.vulnlab.test").match(
        "/tickets/-2001"
    )
    assert endpoint == "tickets.detail" and values == {"ticket_id": -2001}
    for query, expected in [("", 1), ("?page=1000", 1000)]:
        with app.test_request_context("/tickets" + query):
            assert page_number("page") == expected


def test_tickets_cannot_bypass_missing_auth_backend():
    client = create_app().test_client()
    assert client.get("/tickets").status_code == 503
    assert client.get("/healthz").get_json() == {"status": "ok"}
