"""Own display name and minimal administration, with fixed local redirects."""

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from . import account_service as service
from .forms import AccountStatusForm, ProfileForm
from .web_controls import page_number, protected, valid_fields

blueprint = Blueprint("accounts", __name__)


def database():
    return current_app.extensions["database"]


@blueprint.route("/account/edit", methods=["GET", "POST"])
@protected
def edit():
    record = service.profile(database(), current_user)
    form = ProfileForm(obj=record) if request.method == "GET" else ProfileForm()
    error = None
    if request.method == "POST":
        if valid_fields({"display_name"}) and form.validate_on_submit():
            service.edit_profile(database(), current_user, form.display_name.data)
            return redirect(url_for("auth.account"), code=303)
        error = "Invalid display name (1–100 characters). Unexpected or repeated fields are refused."
    return render_template(
        "profile.html", form=form, error=error
    ), 400 if error else 200


@blueprint.get("/admin/users")
@protected
def users():
    service.require_admin(database(), current_user)
    page = page_number("page")
    rows, total = service.list_users(database(), current_user, page)
    return render_template(
        "users.html",
        users=rows,
        total=total,
        page=page,
        page_size=service.PAGE_SIZE,
        max_page=service.MAX_PAGE,
        status_form=AccountStatusForm(),
    )


def status_change(identifier, active):
    service.require_admin(database(), current_user)
    form = AccountStatusForm()
    if not valid_fields(set()) or not form.validate_on_submit():
        abort(400)
    service.change_active(database(), current_user, identifier, active)
    return redirect(url_for("accounts.users"), code=303)


@blueprint.post("/admin/users/<int(signed=True):user_id>/activate")
@protected
def activate(user_id):
    return status_change(user_id, True)


@blueprint.post("/admin/users/<int(signed=True):user_id>/deactivate")
@protected
def deactivate(user_id):
    return status_change(user_id, False)
