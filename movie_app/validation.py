import re
from urllib.parse import urlsplit

from werkzeug.exceptions import BadRequest

TEXT_LIMITS = {"title": 120, "rating": 80, "notes": 5000, "synopsis": 10000, "poster_url": 2048}
STATUSES = {"\u5df2\u770b": True, "\u672a\u770b": False}


def validate_movie(payload, *, creating=False):
    if not isinstance(payload, dict):
        raise BadRequest("\u8bf7\u63d0\u4ea4 JSON \u5bf9\u8c61\u3002")
    data = {}
    if creating and "title" not in payload:
        raise BadRequest("\u8bf7\u586b\u5199\u7535\u5f71\u540d\u79f0\u3002")
    for field, limit in TEXT_LIMITS.items():
        if field not in payload:
            continue
        value = payload[field]
        if not isinstance(value, str):
            raise BadRequest(f"{field} must be a string.")
        value = value.strip() if field != "notes" else value
        if len(value) > limit:
            raise BadRequest(f"{field} must not exceed {limit} characters.")
        if field == "title" and not value:
            raise BadRequest("\u7535\u5f71\u540d\u79f0\u4e0d\u80fd\u4e3a\u7a7a\u3002")
        data[field] = value
    if data.get("poster_url"):
        url = data["poster_url"]
        try:
            parts = urlsplit(url)
            valid_remote = parts.scheme in {"http", "https"} and bool(parts.hostname) and not parts.username and not parts.password
        except ValueError:
            valid_remote = False
        valid_local = re.fullmatch(r"/media/posters/[a-f0-9]{32}\.webp", url) or re.fullmatch(r"/static/posters/[a-z0-9-]+\.(?:jpg|png|webp)", url)
        if not (valid_remote or valid_local) or any(char.isspace() for char in url):
            raise BadRequest("\u6d77\u62a5\u5730\u5740\u5fc5\u987b\u662f HTTP(S) \u56fe\u7247\u94fe\u63a5\u6216\u5df2\u4e0a\u4f20\u7684\u56fe\u7247\u3002")
    if "watched" in payload:
        if type(payload["watched"]) is not bool:
            raise BadRequest("watched must be a boolean.")
        data["watched"] = payload["watched"]
    elif "status" in payload:
        if not isinstance(payload["status"], str) or payload["status"] not in STATUSES:
            raise BadRequest("status must be \u5df2\u770b or \u672a\u770b.")
        data["watched"] = STATUSES[payload["status"]]
    if creating and "id" in payload:
        if not isinstance(payload["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", payload["id"]):
            raise BadRequest("Invalid movie id.")
        data["id"] = payload["id"]
    return data
