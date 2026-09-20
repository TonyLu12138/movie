"""Optional build step. Bundled posters are served locally at runtime."""
from pathlib import Path
from urllib.request import urlopen

POSTERS = {
    "1917": "iZf0KyrE25z1sage4SYFLCCrMi9.jpg",
    "dunkirk": "ebSnODDg9lbsMIaWg2uAbjn7TO5.jpg",
    "forrest-gump": "arw2vcBveWOVZr6pxd9XTd1TdQa.jpg",
    "oppenheimer": "ptpr0kGAckfQkJeJIt8st5dglvd.jpg",
    "shawshank": "9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg",
    "green-book": "7BsvSuDQuoqhWmU2fL7W2GOcZHU.jpg",
}
target = Path(__file__).resolve().parent.parent / "movie_app" / "static" / "posters"
target.mkdir(parents=True, exist_ok=True)
for name, filename in POSTERS.items():
    with urlopen(f"https://image.tmdb.org/t/p/w342/{filename}", timeout=30) as response:
        content = response.read()
    if not content.startswith(b"\xff\xd8"):
        raise ValueError(f"Invalid JPEG: {name}")
    (target / f"{name}.jpg").write_bytes(content)
    print(f"{name}: {len(content)} bytes")
