from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "films.json"


def read_movies():
    if not DATA_FILE.exists():
        return []
    movies = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    # The source database expresses this as a text status. Normalize legacy
    # imports once so the JSON has a real boolean field for the web app.
    changed = False
    for movie in movies:
        expected = movie.get("status") == "\u5df2\u770b"
        if movie.get("watched") != expected:
            movie["watched"] = expected
            changed = True
    if changed:
        DATA_FILE.write_text(json.dumps(movies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return movies


def write_movies(movies):
    DATA_FILE.write_text(json.dumps(movies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class MovieHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if urlparse(self.path).path == "/api/movies":
            return self.send_json(read_movies())
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/movies":
            return self.send_error(HTTPStatus.NOT_FOUND)
        movie = self.read_json()
        movies = read_movies()
        movies.append(movie)
        write_movies(movies)
        return self.send_json(movie, HTTPStatus.CREATED)

    def do_PUT(self):
        movie_id = urlparse(self.path).path.removeprefix("/api/movies/")
        if not movie_id or movie_id == self.path:
            return self.send_error(HTTPStatus.NOT_FOUND)
        movie = self.read_json()
        movies = read_movies()
        for index, existing in enumerate(movies):
            if existing["id"] == movie_id:
                movies[index] = movie
                write_movies(movies)
                return self.send_json(movie)
        return self.send_error(HTTPStatus.NOT_FOUND, "Movie not found")

    def do_DELETE(self):
        movie_id = urlparse(self.path).path.removeprefix("/api/movies/")
        movies = read_movies()
        remaining = [movie for movie in movies if movie["id"] != movie_id]
        if len(remaining) == len(movies):
            return self.send_error(HTTPStatus.NOT_FOUND, "Movie not found")
        write_movies(remaining)
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()


if __name__ == "__main__":
    port = 8000
    print(f"电影库已启动：http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), MovieHandler).serve_forever()
