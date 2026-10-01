"""Application technique locale ; aucun comportement métier."""

from flask import Flask, jsonify


def create_app() -> Flask:
    """Créer un processus HTTP sans connexion à un service externe."""
    app = Flask(__name__, static_folder=None)
    app.config.update(DEBUG=False, TESTING=False)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    return app
