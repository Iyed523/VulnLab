"""Application technique locale ; aucun comportement métier."""

from flask import Flask, jsonify

from .database import environment_config, init_database


def create_app(config=None) -> Flask:
    """Créer un processus HTTP sans connexion à un service externe."""
    app = Flask(__name__, static_folder=None)
    app.config.update(DEBUG=False, TESTING=False)
    app.config.update(environment_config())
    if config is not None:
        app.config.update(config)
    init_database(app)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    return app
