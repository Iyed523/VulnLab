"""Application locale avec authentification de référence."""

from flask import Flask, jsonify

from .auth import init_auth
from .database import environment_config, init_database
from .tickets import blueprint as tickets_blueprint


def create_app(config=None) -> Flask:
    """Créer un processus HTTP sans connexion à un service externe."""
    app = Flask(__name__)
    app.config.update(DEBUG=False, TESTING=False)
    app.config.update(environment_config())
    if config is not None:
        app.config.update(config)
    init_database(app)
    init_auth(app)
    app.register_blueprint(tickets_blueprint)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    return app
