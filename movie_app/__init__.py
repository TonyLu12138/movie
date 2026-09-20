import json
import os
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .extensions import db
from .models import AppSetting
from .services import import_movies, ordered_movies

ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///movies.sqlite3"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        UPLOAD_FOLDER=ROOT / "instance" / "posters",
        SEED_FILE=ROOT / "films.json",
        CATALOG_FILE=ROOT / "movie_app" / "catalog.json",
        AUTO_INIT_DB=True,
        AUTO_IMPORT=os.getenv("AUTO_IMPORT", "true").lower() not in {"0", "false", "no"},
    )
    app.config.update(config or {})
    app.json.ensure_ascii = False
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)

    from .routes import api, pages
    app.register_blueprint(api)
    app.register_blueprint(pages)

    @app.before_request
    def same_origin_writes():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                return jsonify(error="Cross-origin writes are not allowed."), 403

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' https: http: data:; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        response.data = app.json.dumps({"error": error.description})
        response.content_type = "application/json"
        return response

    @app.errorhandler(IntegrityError)
    def conflict_error(error):
        db.session.rollback()
        return jsonify(error="\u6570\u636e\u51b2\u7a81\uff0c\u8bf7\u5237\u65b0\u540e\u91cd\u8bd5\u3002"), 409

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed")
        return jsonify(error="\u6570\u636e\u5e93\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"), 503

    @app.cli.command("init-db")
    def init_db():
        """Create missing tables without removing existing data."""
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("import-json")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--update-existing", is_flag=True, help="Explicitly update matching IDs.")
    def import_json(path, update_existing):
        """Import legacy/backup JSON. Matching IDs are skipped by default."""
        try:
            added, updated = import_movies(path, update_existing=update_existing)
            db.session.commit()
        except (ValueError, OSError) as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Imported {added}; updated {updated}.")

    @app.cli.command("export-json")
    @click.argument("path", type=click.Path(dir_okay=False))
    def export_json(path):
        """Export to a NEW file; never overwrite the source or a prior backup."""
        movies = [movie.to_dict() for movie in db.session.scalars(ordered_movies())]
        try:
            with Path(path).open("x", encoding="utf-8") as target:
                json.dump(movies, target, ensure_ascii=False, indent=2)
                target.write("\n")
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Exported {len(movies)} movies.")

    if app.config["AUTO_INIT_DB"]:
        with app.app_context():
            db.create_all()
            if app.config["AUTO_IMPORT"] and not db.session.get(AppSetting, "legacy_import_v1"):
                seed = Path(app.config["SEED_FILE"])
                if seed.exists():
                    catalog_path = app.config["CATALOG_FILE"]
                    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8")) if catalog_path else {}
                    import_movies(seed, catalog=catalog)
                    db.session.add(AppSetting(key="legacy_import_v1", value="complete"))
                    db.session.commit()
    return app
