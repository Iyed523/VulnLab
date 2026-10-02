"""Reference identity flows; all authentication state is server-side."""

import os
import time
from datetime import timedelta
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFError, CSRFProtect
from limits.errors import StorageError
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth_service import authenticate, load_identity, register_user
from .forms import LoginForm, LogoutForm, RegisterForm
from .session_backend import (
    UNAVAILABLE,
    LabRedisSessionInterface,
    UnavailableSessionInterface,
)

AUTH_ENDPOINTS = {"auth.login", "auth.register", "auth.logout", "auth.account"}


def local_destination(value):
    # Exact allowlist, no URL parsing ambiguities or client-controlled authority.
    return value if value in (None, "", "/account") else None


def init_auth(app):
    for key in ("REDIS_HOST", "REDIS_PASSWORD", "SESSION_KEY_FILE"):
        if key in os.environ:
            app.config.setdefault(key, os.environ[key])
    app.config.setdefault("TRUST_PROXY", os.environ.get("TRUST_PROXY") == "1")
    app.config.update(
        SESSION_COOKIE_NAME="__Host-vulnlab-session",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_PATH="/",
        SESSION_COOKIE_DOMAIN=None,
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=8192,
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_SSL_STRICT=True,
        WTF_CSRF_TIME_LIMIT=900,
    )
    app.config.setdefault("AUTH_SESSION_SECONDS", 1800)
    app.config.setdefault("SESSION_KEY_PREFIX", "vulnlab:session:")
    app.config.setdefault("RATE_KEY_PREFIX", "vulnlab-auth")
    app.config.setdefault("LOGIN_LIMIT", "5 per minute")
    app.config.setdefault("REGISTER_LIMIT", "3 per minute")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        seconds=app.config["AUTH_SESSION_SECONDS"]
    )
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0
        )

    ready = "database" in app.extensions and all(
        app.config.get(key)
        for key in ("REDIS_HOST", "REDIS_PASSWORD", "SESSION_KEY_FILE")
    )
    app.session_interface = UnavailableSessionInterface()
    limiter = None
    if ready:
        try:
            encoded = (
                Path(app.config["SESSION_KEY_FILE"]).read_text(encoding="ascii").strip()
            )
            key = bytes.fromhex(encoded)
            if len(key) != 32:
                raise ValueError
        except (OSError, UnicodeError, ValueError):
            raise ValueError(
                "Invalid local session key file; generate it explicitly"
            ) from None
        app.config["SECRET_KEY"] = key
        client = Redis(
            host=app.config["REDIS_HOST"],
            port=app.config.get("REDIS_PORT", 6379),
            password=app.config["REDIS_PASSWORD"],
            socket_connect_timeout=1,
            socket_timeout=1,
            retry=Retry(NoBackoff(), 0),
        )
        app.extensions["auth_redis"] = client
        app.session_interface = LabRedisSessionInterface(
            app, client, app.config["SESSION_KEY_PREFIX"]
        )
        limiter = Limiter(
            key_func=lambda: request.remote_addr or "unknown",
            app=app,
            default_limits=[],
            storage_uri="redis://localhost:6379",
            storage_options={"connection_pool": client.connection_pool},
            key_prefix=app.config["RATE_KEY_PREFIX"],
            swallow_errors=False,
            in_memory_fallback_enabled=False,
            headers_enabled=False,
        )

    manager = LoginManager(app)
    manager.session_protection = "basic"

    @manager.user_loader
    def user_loader(identifier):
        loaded = load_identity(app.extensions["database"], identifier)
        if loaded is None:
            session.clear()
        return loaded

    @manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for("auth.login", next="/account"), code=303)

    # Must run before CSRF and before views, including sessions whose cookie was replayed.
    @app.before_request
    def require_auth_backend():
        if request.endpoint not in AUTH_ENDPOINTS:
            return None
        if not ready or request.environ.get("vulnlab.session_unavailable"):
            return UNAVAILABLE, 503
        app.extensions["auth_redis"].ping()
        if "_user_id" in session:
            if time.time() >= session.get("_expires_at", 0):
                session.clear()
            else:
                # Trigger a fresh SQL active-state check on every auth request.
                if not current_user.is_authenticated:
                    session.clear()
        return None

    CSRFProtect(app)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return "Invalid or missing CSRF token.", 400

    def backend_error(error):
        session.clear()
        return UNAVAILABLE, 503

    for error_type in (RedisError, StorageError, SQLAlchemyError):
        app.register_error_handler(error_type, backend_error)

    @app.errorhandler(429)
    def limited(error):
        return "Too many attempts. Try again later.", 429

    @app.after_request
    def private_response(response):
        if request.endpoint in AUTH_ENDPOINTS:
            response.headers["Cache-Control"] = "no-store"
        return response

    blueprint = Blueprint("auth", __name__)

    @blueprint.route("/register", methods=["GET", "POST"])
    def register():
        form = RegisterForm()
        error = None
        status = 200
        if request.method == "POST":
            allowed = {"username", "display_name", "password", "csrf_token", "submit"}
            if set(request.form) - allowed or any(
                len(request.form.getlist(k)) != 1 for k in request.form
            ):
                error, status = "Unexpected registration fields.", 400
            elif not form.validate_on_submit():
                error, status = "Invalid registration fields.", 400
            elif register_user(
                current_app.extensions["database"],
                form.username.data,
                form.display_name.data,
                form.password.data,
            ):
                return redirect(url_for("auth.login"), code=303)
            else:
                error, status = "Unable to register this username.", 409
        return render_template("register.html", form=form, error=error), status

    @blueprint.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        error = None
        status = 200
        destination = request.args.get("next")
        if local_destination(destination) is None and destination not in (None, ""):
            return "Redirect destination not allowed.", 400
        if request.method == "POST":
            if set(request.form) - {
                "username",
                "password",
                "csrf_token",
                "submit",
            } or any(len(request.form.getlist(k)) != 1 for k in request.form):
                return "Unexpected login fields.", 400
            if not form.validate_on_submit():
                error, status = "Invalid credentials.", 401
            else:
                user = authenticate(
                    app.extensions["database"], form.username.data, form.password.data
                )
                if user is None:
                    error, status = "Invalid credentials.", 401
                else:
                    # regenerate only acts on a nonempty session (verified in 0.8.0).
                    # Retain its CSRF entry until the old key is deleted, then clear it.
                    app.session_interface.regenerate(session)
                    session.clear()
                    session.permanent = True
                    login_user(user, remember=False, fresh=True)
                    session["_expires_at"] = (
                        time.time() + app.config["AUTH_SESSION_SECONDS"]
                    )
                    return redirect(destination or url_for("auth.account"), code=303)
        return render_template("login.html", form=form, error=error), status

    @blueprint.post("/logout")
    @login_required
    def logout():
        logout_user()
        session.clear()
        return redirect(url_for("auth.login"), code=303)

    @blueprint.get("/account")
    @login_required
    def account():
        return render_template("account.html", logout_form=LogoutForm())

    if limiter is not None:
        login = limiter.limit(app.config["LOGIN_LIMIT"], methods=["POST"])(login)
        register = limiter.limit(app.config["REGISTER_LIMIT"], methods=["POST"])(
            register
        )
        # Blueprint deferred routes retain originals; decorate before their execution
        # via replacing the registered view after registration instead.
    app.register_blueprint(blueprint)
    if limiter is not None:
        app.view_functions["auth.login"] = login
        app.view_functions["auth.register"] = register
