import hashlib
import json
from unittest.mock import patch
from movie_app import ROOT, create_app
from movie_app.extensions import db
from movie_app.services import import_movies


def test_original_collection_imported_once_without_modification(app_config):
    source = ROOT / "films.json"
    original = source.read_bytes()
    records = json.loads(original.decode("utf-8-sig"))
    config = {**app_config, "AUTO_IMPORT": True, "SEED_FILE": source}
    first = create_app(config)
    client = first.test_client()
    imported = client.get("/api/movies").json
    assert len(imported) == len(records) == 166
    for record, movie in zip(records, imported):
        assert all(movie[key] == value for key, value in record.items() if key != "status")
        assert movie["status"] == ("\u5df2\u770b" if record["watched"] else "\u672a\u770b")
    client.patch(f"/api/movies/{records[0]['id']}", json={"notes": "Do not overwrite"})
    client.delete(f"/api/movies/{records[1]['id']}")
    with first.app_context():
        db.session.remove()
        db.engine.dispose()
    second = create_app(config)
    saved = second.test_client().get("/api/movies").json
    assert len(saved) == 165
    assert saved[0]["notes"] == "Do not overwrite"
    assert not any(movie["id"] == records[1]["id"] for movie in saved)
    for movie in saved:
        second.test_client().delete(f"/api/movies/{movie['id']}")
    with second.app_context():
        db.session.remove()
        db.engine.dispose()
    third = create_app(config)
    assert third.test_client().get("/api/movies").json == []
    with third.app_context():
        db.session.remove()
        db.engine.dispose()
    assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(original).digest()


def test_import_export_and_explicit_updates(app, client, movie, tmp_path):
    runner = app.test_cli_runner()
    backup = tmp_path / "backup.json"
    assert runner.invoke(args=["export-json", str(backup)]).exit_code == 0
    assert runner.invoke(args=["export-json", str(backup)]).exit_code != 0
    assert json.loads(backup.read_text(encoding="utf-8"))[0]["poster_url"] == movie["poster_url"]
    client.patch(f"/api/movies/{movie['id']}", json={"notes": "Keep this"})
    assert runner.invoke(args=["import-json", str(backup)]).exit_code == 0
    assert client.get(f"/api/movies/{movie['id']}").json["notes"] == "Keep this"
    assert runner.invoke(args=["import-json", str(backup), "--update-existing"]).exit_code == 0
    assert client.get(f"/api/movies/{movie['id']}").json["notes"] == movie["notes"]


def test_invalid_import_is_atomic(app, client, tmp_path):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps([{"id": "valid", "title": "Valid"}, {"id": "bad", "title": ""}]), encoding="utf-8")
    result = app.test_cli_runner().invoke(args=["import-json", str(source)])
    assert result.exit_code != 0
    assert client.get("/api/movies").json == []


def test_catalog_only_fills_missing_fields(app_config, tmp_path):
    source = tmp_path / "seed.json"
    catalog = tmp_path / "catalog.json"
    source.write_text(json.dumps([{"id": "one", "title": "Known", "synopsis": "My own synopsis"}]), encoding="utf-8")
    catalog.write_text(json.dumps({"Known": {"poster_url": "https://example.com/a.jpg", "synopsis": "Default synopsis"}}), encoding="utf-8")
    app = create_app({**app_config, "AUTO_IMPORT": True, "SEED_FILE": source, "CATALOG_FILE": catalog})
    movie = app.test_client().get("/api/movies").json[0]
    assert movie["synopsis"] == "My own synopsis"
    assert movie["poster_url"] == "https://example.com/a.jpg"
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_public_checkout_uses_remote_poster_sources(app, client):
    catalog = json.loads((ROOT / "movie_app" / "catalog.json").read_text(encoding="utf-8"))
    with app.app_context(), patch("movie_app.services.Path.is_file", return_value=False):
        import_movies(ROOT / "films.json", catalog=catalog)
        db.session.commit()
    movies = client.get("/api/movies").json
    for movie in movies:
        if movie["title"] in catalog:
            assert movie["poster_url"] == catalog[movie["title"]]["poster_source"]
        else:
            assert movie["poster_url"] == ""
