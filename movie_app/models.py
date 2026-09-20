from datetime import datetime, timezone
from uuid import uuid4

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Movie(db.Model):
    __tablename__ = "movies"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id = db.Column(db.String(64), primary_key=True, default=lambda: str(uuid4()))
    title = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.String(80), nullable=False, default="")
    watched = db.Column(db.Boolean, nullable=False, default=False, index=True)
    notes = db.Column(db.Text, nullable=False, default="")
    poster_url = db.Column(db.String(2048), nullable=False, default="")
    synopsis = db.Column(db.Text, nullable=False, default="")
    # Preserve the original JSON order while putting new additions first.
    position = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "rating": self.rating,
            "watched": self.watched,
            "status": "\u5df2\u770b" if self.watched else "\u672a\u770b",
            "notes": self.notes,
            "poster_url": self.poster_url,
            "synopsis": self.synopsis,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False)
