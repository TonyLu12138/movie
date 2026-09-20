from io import BytesIO

from PIL import Image
import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from movie_app import create_app
from movie_app.extensions import db
from movie_app.models import Movie, AppSetting


def test_crud_and_legacy_put(client, movie):
    movie_id = movie["id"]
    assert client.get("/api/movies").json == [movie]
    assert client.get(f"/api/movies/{movie_id}").json == movie
    updated = client.put(f"/api/movies/{movie_id}", json={
        "id": movie_id, "title": "New title", "rating": "Great", "watched": True,
        "status": "\u672a\u770b", "notes": "New note",
    })
    assert updated.status_code == 200
    assert updated.json["status"] == "\u5df2\u770b"
    assert updated.json["synopsis"] == movie["synopsis"]
    assert updated.json["poster_url"] == movie["poster_url"]
    assert client.delete(f"/api/movies/{movie_id}").status_code == 204
    assert client.get(f"/api/movies/{movie_id}").status_code == 404
    assert client.get("/api/movies").json == []


def test_patch_notes_and_status_do_not_clobber_other_fields(client, movie):
    path = f"/api/movies/{movie['id']}"
    note = "  \u559c\u6b22\u8fd9\u4e2a\u7ed3\u5c3e\n\u7b2c\u4e8c\u884c \U0001f3ac  "
    response = client.patch(path, json={"notes": note})
    assert response.json["notes"] == note
    assert response.json["synopsis"] == movie["synopsis"]
    response = client.patch(path, json={"watched": True})
    assert response.json["notes"] == note
    assert response.json["poster_url"] == movie["poster_url"]
    assert response.json["updated_at"] >= movie["updated_at"]


def test_status_only_legacy_client(client):
    response = client.post("/api/movies", json={"title": "Legacy", "status": "\u5df2\u770b"})
    assert response.json["watched"] is True


@pytest.mark.parametrize("payload", [None, [], "movie", {}, {"title": " "}, {"title": 5},
    {"title": "x" * 121}, {"title": "Valid", "watched": "false"},
    {"title": "Valid", "watched": 1}, {"title": "Valid", "notes": None},
    {"title": "Valid", "notes": "x" * 5001}, {"title": "Valid", "synopsis": "x" * 10001},
    {"title": "Valid", "rating": "x" * 81}, {"title": "Valid", "id": "../file"},
    {"title": "Valid", "status": []}])
def test_invalid_input(client, payload):
    response = client.post("/api/movies", json=payload) if payload is not None else client.post("/api/movies", data="null", content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json
    assert client.get("/api/movies").json == []


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:image/svg+xml,evil", "file:///etc/passwd", "//example.com/x.jpg", "/.env", "https://[invalid", "https://user:secret@example.com/a.jpg", "https://example.com/bad url.jpg"])
def test_reject_unsafe_poster_urls(client, url):
    assert client.post("/api/movies", json={"title": "Test", "poster_url": url}).status_code == 400


def test_invalid_requests_leave_existing_data(client, movie):
    path = f"/api/movies/{movie['id']}"
    assert client.patch(path, json={"id": "changed"}).status_code == 400
    assert client.patch(path, json=[]).status_code == 400
    assert client.patch(path, data="{invalid", content_type="application/json").status_code == 400
    assert client.patch(path, data="text").status_code == 415
    assert client.get(path).json == movie
    assert client.post("/api/movies", json=movie).status_code == 409


def test_filters_and_literal_search(client, movie):
    client.post("/api/movies", json={"title": "100%_test", "watched": True, "notes": "special \u5907\u6ce8"})
    assert len(client.get("/api/movies?status=watched").json) == 1
    assert client.get("/api/movies?status=unwatched").json[0]["id"] == movie["id"]
    assert len(client.get("/api/movies", query_string={"q": "%_"}).json) == 1
    assert len(client.get("/api/movies", query_string={"q": "SYNOPSIS"}).json) == 1
    assert len(client.get("/api/movies", query_string={"q": "\u5907\u6ce8"}).json) == 1
    assert client.get("/api/movies?status=invalid").status_code == 400


def test_unknown_routes_and_source_are_not_exposed(client):
    for path in ["/films.json", "/app.py", "/.env", "/.git/config", "/api/movies/missing", "/static/../../films.json"]:
        response = client.get(path)
        assert response.status_code == 404
        assert "error" in response.json
    assert client.delete("/api/movies/missing").status_code == 404
    assert client.patch("/api/movies/missing", json={}).status_code == 404
    assert client.post("/api/movies/missing", json={}).status_code == 405


def test_security_headers_and_cross_origin_writes(client):
    assert client.get("/").status_code == 200
    response = client.get("/api/movies")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.post("/api/movies", json={"title": "No"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/movies", json={"title": "Yes"}, headers={"Origin": "http://localhost"}).status_code == 201


def test_poster_upload_and_serve(client, movie):
    buffer = BytesIO()
    Image.new("RGB", (80, 120), "red").save(buffer, "PNG")
    buffer.seek(0)
    response = client.post("/api/posters", data={"file": (buffer, "../../poster.png")})
    assert response.status_code == 201
    url = response.json["poster_url"]
    assert url.startswith("/media/posters/") and url.endswith(".webp")
    image = client.get(url)
    assert image.status_code == 200
    assert image.content_type == "image/webp"
    assert Image.open(BytesIO(image.data)).size == (80, 120)
    assert client.patch(f"/api/movies/{movie['id']}", json={"poster_url": url}).status_code == 200


def test_invalid_and_oversize_uploads(client):
    assert client.post("/api/posters").status_code == 400
    assert client.post("/api/posters", data={"file": (BytesIO(b"not an image"), "poster.png")}).status_code == 400
    assert client.post("/api/posters", data={"file": (BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "poster.png")}).status_code == 400
    assert client.post("/api/posters", data=b"x" * (7 * 1024 * 1024), content_type="application/octet-stream").status_code == 413


def test_persistence_after_app_restart(app, app_config, client, movie):
    client.patch(f"/api/movies/{movie['id']}", json={"notes": "Saved across restart"})
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    restarted = create_app(app_config)
    assert restarted.test_client().get(f"/api/movies/{movie['id']}").json["notes"] == "Saved across restart"
    with restarted.app_context():
        db.session.remove()
        db.engine.dispose()


def test_mysql_schema_compiles_without_mysql_server():
    for model in [Movie, AppSetting]:
        sql = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        assert "CREATE TABLE" in sql
    movie_sql = str(CreateTable(Movie.__table__).compile(dialect=mysql.dialect()))
    assert "utf8mb4" in movie_sql
    assert "VARCHAR(2048)" in movie_sql
