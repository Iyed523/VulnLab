"""Shared HTTP guards; protected views carry their own authentication policy."""

from flask import abort, current_app, request
from flask_login import login_required

PAGE_SIZE = 20
MAX_PAGE = 1000


def protected(view):
    wrapped = login_required(view)
    wrapped.vulnlab_protected = True
    return wrapped


def is_protected():
    view = current_app.view_functions.get(request.endpoint)
    return bool(view and getattr(view, "vulnlab_protected", False))


def page_number(name):
    raw = request.args.getlist(name)
    if not raw:
        return 1
    if len(raw) != 1 or not raw[0].isascii() or not raw[0].isdigit() or len(raw[0]) > 4:
        abort(400)
    page = int(raw[0])
    if not 1 <= page <= MAX_PAGE:
        abort(400)
    return page


def valid_fields(allowed):
    return not (set(request.form) - set(allowed) - {"csrf_token", "submit"}) and all(
        len(request.form.getlist(key)) == 1 for key in request.form
    )
