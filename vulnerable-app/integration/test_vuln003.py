"""VULN-003 disclosure versus retained protections, on disposable real stores."""

import pytest
from sqlalchemy import func, select

from vulnlab_vulnerable.models import Comment, Ticket

from .test_auth import BASE
from .test_auth import auth_app as auth_app
from .test_tickets import ALICE, BOB, actor_client, ticket_post


@pytest.mark.vulnerable_behavior
@pytest.mark.parametrize("identifier,marker", [(ALICE, "Alice"), (BOB, "Bob")])
def test_other_users_ticket_and_comments_disclosed(auth_app, identifier, marker):
    actor = "bob" if identifier == ALICE else "alice"
    client = actor_client(auth_app, actor)
    listing = client.get("/tickets", base_url=BASE).get_data(as_text=True)
    assert f"{marker} demo ticket" not in listing
    assert "Total visible: 1" in listing
    response = client.get(f"/tickets/{identifier}", base_url=BASE)
    assert response.status_code == 200  # Expected weakness; baseline returned 404.
    body = response.get_data(as_text=True)
    assert f"{marker} demo ticket" in body
    assert f"Fictitious private {marker} data" in body
    assert f"{marker} fictitious comment" in body
    assert "Status:" in body and "Comments (" in body
    if identifier == ALICE:
        assert "Admin fictitious response to Alice" in body
        assert "Admin fictif" in body
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.vulnerable_behavior
def test_disclosed_comments_are_paginated_and_html_escaped(auth_app):
    db = auth_app.extensions["database"]
    with db.transaction() as session:
        ticket = session.get(Ticket, ALICE)
        ticket.title = "<b>VULN-003 title</b>"
        ticket.description = "<script>VULN-003 description</script>"
        for i in range(21):
            session.add(
                Comment(
                    ticket_id=ALICE, author_id=-1001, content=f"<b>marker {i:02}</b>"
                )
            )
    client = actor_client(auth_app, "bob")
    first = client.get(f"/tickets/{ALICE}", base_url=BASE).get_data(as_text=True)
    second = client.get(f"/tickets/{ALICE}?comments_page=2", base_url=BASE).get_data(
        as_text=True
    )
    assert "&lt;b&gt;VULN-003 title&lt;/b&gt;" in first
    assert "&lt;script&gt;VULN-003 description&lt;/script&gt;" in first
    assert "<script>VULN-003" not in first
    assert first.count("&lt;b&gt;marker") == 18 and second.count("&lt;b&gt;marker") == 3
    assert "Comments (23)" in first


@pytest.mark.preserved_protection
@pytest.mark.parametrize(
    "suffix,method,data",
    [
        ("/edit", "GET", {}),
        (
            "/edit",
            "POST",
            {"title": "Denied", "description": "Denied", "status": "closed"},
        ),
        ("/delete", "POST", {}),
        ("/comments", "POST", {"content": "Denied"}),
        ("", "HEAD", {}),
    ],
)
def test_disclosure_never_grants_write_or_head_access(auth_app, suffix, method, data):
    client = actor_client(auth_app, "bob")
    assert client.get(f"/tickets/{ALICE}", base_url=BASE).status_code == 200
    response = (
        ticket_post(client, f"/tickets/{ALICE}{suffix}", data)
        if method == "POST"
        else client.open(f"/tickets/{ALICE}{suffix}", method=method, base_url=BASE)
    )
    assert response.status_code == 404
    with auth_app.extensions["database"].transaction() as session:
        ticket = session.get(Ticket, ALICE)
        assert ticket.title == "Alice demo ticket" and ticket.status == "open"
        assert ticket.owner_id == -1001
        assert session.scalar(select(func.count()).select_from(Comment)) == 3


@pytest.mark.preserved_protection
@pytest.mark.parametrize("identifier", [-9999, 2**40, -(2**40)])
def test_missing_detail_still_404(auth_app, identifier):
    client = actor_client(auth_app, "bob")
    response = client.get(f"/tickets/{identifier}", base_url=BASE)
    assert response.status_code == 404
    assert "Alice demo ticket" not in response.get_data(as_text=True)
