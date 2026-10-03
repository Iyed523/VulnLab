"""Redis-only sessions; failures never fall back to signed client sessions."""

import time
from datetime import timedelta

import msgspec
from flask import request
from flask.sessions import SessionInterface
from flask_session.redis import RedisSession, RedisSessionInterface
from redis.exceptions import RedisError

UNAVAILABLE = "Authentication service temporarily unavailable."


def delete_cookie(app, response):
    response.delete_cookie(
        app.config["SESSION_COOKIE_NAME"],
        path="/",
        secure=True,
        httponly=True,
        samesite="Lax",
    )


class UnavailableSessionInterface(SessionInterface):
    def open_session(self, app, req):
        req.environ["vulnlab.session_unavailable"] = True
        return RedisSession()

    def save_session(self, app, session, response):
        # There is intentionally no backing store or cookie in this state.
        return None


class StrictSerializer:
    def encode(self, session):
        return msgspec.msgpack.encode(dict(session))

    def decode(self, data):
        return msgspec.msgpack.decode(data, type=dict)


class LabRedisSessionInterface(RedisSessionInterface):
    def __init__(self, app, client, prefix):
        super().__init__(
            app,
            client=client,
            key_prefix=prefix,
            permanent=True,
            sid_length=32,
            serialization_format="msgpack",
        )
        self.serializer = StrictSerializer()

    def open_session(self, app, req):
        if req.path == "/healthz" or req.path.startswith("/static/"):
            return self.session_class()
        try:
            return super().open_session(app, req)
        except (RedisError, msgspec.DecodeError):
            req.environ["vulnlab.session_unavailable"] = True
            return self.session_class()

    def _upsert_session(self, lifetime, session, store_id):
        # Absolute authenticated lifetime; writes must not restart its countdown.
        if "_expires_at" in session:
            seconds = max(1, int(session["_expires_at"] - time.time()))
            lifetime = timedelta(seconds=min(seconds, int(lifetime.total_seconds())))
        super()._upsert_session(lifetime, session, store_id)

    def save_session(self, app, session, response):
        if request.path == "/healthz" or request.path.startswith("/static/"):
            return
        if request.environ.get("vulnlab.session_unavailable"):
            delete_cookie(app, response)
            return
        try:
            super().save_session(app, session, response)
            if not session and session.modified:
                # Flask-Session's deletion omits security attributes; enforce ours.
                response.headers.pop("Set-Cookie", None)
                delete_cookie(app, response)
        except RedisError:
            # Saving occurs after error handlers; replace any success/identity response.
            response.status_code = 503
            response.set_data(UNAVAILABLE)
            response.headers.pop("Location", None)
            response.headers.pop("Set-Cookie", None)
            response.headers["Cache-Control"] = "no-store"
            delete_cookie(app, response)
