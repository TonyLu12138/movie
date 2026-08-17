"""Normalize the legacy text status into the JSON boolean used by the app."""
import json
from pathlib import Path

path = Path("films.json")
movies = json.loads(path.read_text(encoding="utf-8-sig"))
for movie in movies:
    movie["watched"] = movie.get("status") == "\u5df2\u770b"
path.write_text(json.dumps(movies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Normalized {len(movies)} movies")
