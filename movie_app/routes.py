from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from flask import Blueprint, current_app, jsonify, render_template, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from .extensions import db
from .models import Movie
from .services import ordered_movies
from .validation import validate_movie

api = Blueprint("api", __name__, url_prefix="/api")
pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    return render_template("index.html")


@pages.get("/media/posters/<filename>")
def poster(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, max_age=86400)


def find_movie(movie_id):
    movie = db.session.get(Movie, movie_id)
    if movie is None:
        raise NotFound("\u7535\u5f71\u4e0d\u5b58\u5728\u6216\u5df2\u88ab\u5220\u9664\u3002")
    return movie


@api.get("/movies")
def list_movies():
    statement = ordered_movies()
    status = request.args.get("status", "all")
    if status not in {"all", "watched", "unwatched"}:
        raise BadRequest("Invalid status filter.")
    if status != "all":
        statement = statement.where(Movie.watched.is_(status == "watched"))
    query = request.args.get("q", "").strip()
    if query:
        statement = statement.where(db.or_(*[
            column.icontains(query, autoescape=True)
            for column in (Movie.title, Movie.rating, Movie.notes, Movie.synopsis)
        ]))
    return jsonify([movie.to_dict() for movie in db.session.scalars(statement)])


@api.get("/movies/<movie_id>")
def movie_detail(movie_id):
    return jsonify(find_movie(movie_id).to_dict())


@api.post("/movies")
def add_movie():
    data = validate_movie(request.get_json(), creating=True)
    if data.get("id") and db.session.get(Movie, data["id"]):
        raise Conflict("\u8be5\u7535\u5f71 ID \u5df2\u5b58\u5728\u3002")
    position = (db.session.scalar(db.select(db.func.max(Movie.position))) or 0) + 1
    movie = Movie(**data, position=position)
    db.session.add(movie)
    db.session.commit()
    return jsonify(movie.to_dict()), 201


@api.route("/movies/<movie_id>", methods=["PUT", "PATCH"])
def update_movie(movie_id):
    movie = find_movie(movie_id)
    payload = request.get_json()
    data = validate_movie(payload)
    if "id" in payload and payload["id"] != movie_id:
        raise BadRequest("Movie id cannot be changed.")
    for field, value in data.items():
        setattr(movie, field, value)
    db.session.commit()
    return jsonify(movie.to_dict())


@api.delete("/movies/<movie_id>")
def delete_movie(movie_id):
    db.session.delete(find_movie(movie_id))
    db.session.commit()
    return "", 204


@api.post("/posters")
def upload_poster():
    uploaded = request.files.get("file")
    if uploaded is None:
        raise BadRequest("\u8bf7\u9009\u62e9\u6d77\u62a5\u56fe\u7247\u3002")
    content = uploaded.stream.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise BadRequest("\u6d77\u62a5\u5927\u5c0f\u4e0d\u80fd\u8d85\u8fc7 5 MB\u3002")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image format")
                if source.width * source.height > 20_000_000:
                    raise ValueError("Image dimensions too large")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1200, 1800))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise BadRequest("\u8bf7\u4e0a\u4f20\u6709\u6548\u7684 JPG\u3001PNG \u6216 WebP \u56fe\u7247\uff08\u4e0d\u8d85\u8fc7 2000 \u4e07\u50cf\u7d20\uff09\u3002") from exc
    filename = uuid4().hex + ".webp"
    image.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename, format="WEBP", quality=88)
    return jsonify({"poster_url": f"/media/posters/{filename}"}), 201
