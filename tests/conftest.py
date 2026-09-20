import pytest

from movie_app import create_app
from movie_app.extensions import db


def pytest_addoption(parser):
    parser.addoption("--run-browser", action="store_true", default=False)
    parser.addoption("--browser-channel", default="msedge")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-browser"):
        for item in items:
            if "browser" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Use --run-browser for UI tests."))


@pytest.fixture
def app_config(tmp_path):
    return {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.sqlite3").as_posix(),
        "UPLOAD_FOLDER": tmp_path / "posters",
        "AUTO_IMPORT": False,
        "CATALOG_FILE": None,
    }


@pytest.fixture
def app(app_config):
    application = create_app(app_config)
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def movie(client):
    response = client.post("/api/movies", json={
        "title": "\u6d4b\u8bd5\u7535\u5f71", "rating": "4.5/5", "watched": False,
        "notes": "original note", "synopsis": "A test synopsis.",
        "poster_url": "https://example.com/poster.jpg",
    })
    assert response.status_code == 201
    return response.json
