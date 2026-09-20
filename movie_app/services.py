import json
from pathlib import Path

from werkzeug.exceptions import BadRequest

from .extensions import db
from .models import Movie
from .validation import validate_movie


def import_movies(path, *, update_existing=False, catalog=None):
    """Validate a whole import before writing; never delete existing records."""
    records = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(records, list):
        raise ValueError("The import must contain a JSON array.")
    validated = []
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("id"):
            raise ValueError(f"Record {index + 1} needs a stable id.")
        record = dict(record)
        metadata = (catalog or {}).get(record.get("title"), {})
        for field in ("poster_url", "synopsis"):
            if field not in metadata:
                continue
            value = metadata[field]
            if field == "poster_url" and value.startswith("/static/posters/"):
                local_file = Path(__file__).resolve().parent / value.lstrip("/")
                if not local_file.is_file():
                    value = metadata.get("poster_source", "")
            record.setdefault(field, value)
        # The old Notion importer treated its text status as authoritative.
        if "watched" not in record or type(record["watched"]) is not bool:
            record["watched"] = record.get("status") == "\u5df2\u770b"
        try:
            data = validate_movie(record, creating=True)
        except BadRequest as exc:
            raise ValueError(f"Record {index + 1}: {exc.description}") from exc
        if data["id"] in seen:
            raise ValueError(f"Duplicate id: {data['id']}")
        seen.add(data["id"])
        validated.append(data)
    added = updated = 0
    minimum = db.session.scalar(db.select(db.func.min(Movie.position))) or 0
    for index, data in enumerate(validated):
        existing = db.session.get(Movie, data["id"])
        if existing:
            if update_existing:
                for field, value in data.items():
                    setattr(existing, field, value)
                updated += 1
        else:
            db.session.add(Movie(**data, position=minimum - index - 1))
            added += 1
    db.session.flush()
    return added, updated


def ordered_movies():
    return db.select(Movie).order_by(Movie.position.desc(), Movie.created_at.desc(), Movie.id)
