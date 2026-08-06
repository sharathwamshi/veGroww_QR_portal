import os

from flask import Flask, render_template, send_from_directory

from config import Config
from extensions import db


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Make sure every local storage folder exists on startup
    for folder in (
        app.config["PHOTO_DIR"],
        app.config["LOGO_DIR"],
        app.config["SIGNATURE_DIR"],
        app.config["ID_CARD_DIR"],
        app.config["QR_DIR"],
        app.config["IMAGE_QR_SOURCE_DIR"],
        app.config["VCARD_IMAGE_DIR"],
        app.config["INVITE_IMAGE_DIR"],
    ):
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)

    # ---- Blueprints ----
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.id_cards import id_cards_bp
    from routes.image_qr import image_qr_bp
    from routes.upi_qr import upi_qr_bp
    from routes.invitation import invitation_bp
    from routes.url_qr import url_qr_bp
    from routes.vcard import vcard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(id_cards_bp)
    app.register_blueprint(image_qr_bp)
    app.register_blueprint(upi_qr_bp)
    app.register_blueprint(vcard_bp)
    app.register_blueprint(url_qr_bp)
    app.register_blueprint(invitation_bp)

    # ---- Local file serving for generated/uploaded assets ----
    @app.route("/media/photos/<path:filename>")
    def media_photo(filename):
        return send_from_directory(app.config["PHOTO_DIR"], filename)

    @app.route("/media/logos/<path:filename>")
    def media_logo(filename):
        return send_from_directory(app.config["LOGO_DIR"], filename)

    @app.route("/media/signatures/<path:filename>")
    def media_signature(filename):
        return send_from_directory(app.config["SIGNATURE_DIR"], filename)

    @app.route("/media/id-cards/<path:filename>")
    def media_card(filename):
        return send_from_directory(app.config["ID_CARD_DIR"], filename)

    @app.route("/media/qr/<path:filename>")
    def media_qr(filename):
        return send_from_directory(app.config["QR_DIR"], filename)

    # ---- Template globals ----
    @app.context_processor
    def inject_globals():
        # platform_meta is used by the public vCard page to render social chips
        from utils.vcard_utils import platform_meta
        return {
            "app_name": app.config["APP_NAME"],
            "app_tagline": app.config["APP_TAGLINE"],
            "platform_meta": platform_meta,
        }

    # ---- Error pages ----
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("404.html", message="Uploaded file is too large."), 413

    # Create tables on boot unless AUTO_CREATE_TABLES=0 (e.g. schema.sql
    # was imported manually and the DB user has no DDL rights).
    if app.config.get("AUTO_CREATE_TABLES", True):
        with app.app_context():
            db.create_all()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        debug=application.config["FLASK_DEBUG"],
        host=application.config["FLASK_HOST"],
        port=application.config["FLASK_PORT"],
    )