"""Local ticket routes; authorization is enforced independently of the UI."""

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from . import ticket_service as service
from .forms import CommentForm, DeleteTicketForm, EditTicketForm, TicketForm
from .web_controls import page_number, protected, valid_fields

blueprint = Blueprint("tickets", __name__)


def database():
    return current_app.extensions["database"]


@blueprint.get("/tickets")
@protected
def index():
    page = page_number("page")
    rows, total = service.list_tickets(database(), current_user, page)
    return render_template(
        "tickets/index.html",
        tickets=rows,
        total=total,
        page=page,
        page_size=service.PAGE_SIZE,
        max_page=service.MAX_PAGE,
    )


@blueprint.route("/tickets/new", methods=["GET", "POST"])
@protected
def new():
    form = TicketForm()
    error = None
    if request.method == "POST":
        if valid_fields({"title", "description"}) and form.validate_on_submit():
            identifier = service.create_ticket(
                database(), current_user, form.title.data, form.description.data
            )
            return redirect(url_for("tickets.detail", ticket_id=identifier), code=303)
        error = "Invalid fields. Title: 1–200; description: 1–10000 characters. Unexpected or repeated fields are refused."
    return render_template(
        "tickets/form.html", form=form, error=error, editing=False
    ), 400 if error else 200


@blueprint.get("/tickets/<int(signed=True):ticket_id>")
@protected
def detail(ticket_id):
    page = page_number("comments_page")
    ticket, comments, total = service.ticket_detail(
        database(), current_user, ticket_id, page
    )
    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        comments=comments,
        total=total,
        page=page,
        page_size=service.PAGE_SIZE,
        max_page=service.MAX_PAGE,
        comment_form=CommentForm(),
        delete_form=DeleteTicketForm(),
        error=None,
    )


@blueprint.route("/tickets/<int(signed=True):ticket_id>/edit", methods=["GET", "POST"])
@protected
def edit(ticket_id):
    ticket, _, _ = service.ticket_detail(database(), current_user, ticket_id, 1)
    form = EditTicketForm(obj=ticket) if request.method == "GET" else EditTicketForm()
    error = None
    if request.method == "POST":
        if (
            valid_fields({"title", "description", "status"})
            and form.validate_on_submit()
        ):
            service.edit_ticket(
                database(),
                current_user,
                ticket_id,
                form.title.data,
                form.description.data,
                form.status.data,
            )
            return redirect(url_for("tickets.detail", ticket_id=ticket_id), code=303)
        error = "Invalid fields or status. Owner, identifiers and dates cannot be changed; repeated fields are refused."
    return render_template(
        "tickets/form.html", form=form, error=error, editing=True
    ), 400 if error else 200


@blueprint.post("/tickets/<int(signed=True):ticket_id>/delete")
@protected
def delete(ticket_id):
    service.ticket_detail(database(), current_user, ticket_id, 1)
    form = DeleteTicketForm()
    if not valid_fields(set()) or not form.validate_on_submit():
        return "Invalid deletion fields.", 400
    service.delete_ticket(database(), current_user, ticket_id)
    return redirect(url_for("tickets.index"), code=303)


@blueprint.post("/tickets/<int(signed=True):ticket_id>/comments")
@protected
def comment(ticket_id):
    ticket, comments, total = service.ticket_detail(
        database(), current_user, ticket_id, 1
    )
    form = CommentForm()
    if valid_fields({"content"}) and form.validate_on_submit():
        service.add_comment(database(), current_user, ticket_id, form.content.data)
        return redirect(url_for("tickets.detail", ticket_id=ticket_id), code=303)
    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        comments=comments,
        total=total,
        page=1,
        page_size=service.PAGE_SIZE,
        max_page=service.MAX_PAGE,
        comment_form=form,
        delete_form=DeleteTicketForm(),
        error="Invalid comment (1–5000 characters); unexpected or repeated fields are refused.",
    ), 400
