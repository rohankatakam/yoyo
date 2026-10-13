"""Read-only Apple authorization adapter, adapted from FYE/apple/common.py.
Explicitly authorized by the user; never store or trace returned headers.
"""

import base64
import json
import plistlib
import sqlite3
import time
from pathlib import Path

PODCASTS_CACHE_DB = (
    Path.home()
    / "Library/Containers/com.apple.podcasts/Data/Library/Caches/com.apple.podcasts/Cache.db"
)


class AppleAuthorizationError(RuntimeError):
    pass


def local_podcasts_headers(cache_db: Path = PODCASTS_CACHE_DB) -> dict[str, str]:
    """Read the newest AMP request headers from Podcasts' URL cache."""
    if not cache_db.exists():
        raise AppleAuthorizationError(
            f"Podcasts cache database does not exist: {cache_db}"
        )

    uri = f"file:{cache_db}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            row = connection.execute(
                """
                SELECT b.request_object
                FROM cfurl_cache_blob_data AS b
                JOIN cfurl_cache_response AS r USING(entry_ID)
                WHERE r.request_key LIKE 'https://amp-api.podcasts.apple.com/%'
                ORDER BY r.entry_ID DESC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.Error as exc:
        raise AppleAuthorizationError(f"could not read Podcasts cache: {exc}") from exc
    if not row or not row[0]:
        raise AppleAuthorizationError(
            "Podcasts cache contains no Apple catalog authorization"
        )

    try:
        archive = plistlib.loads(row[0])
        cached = archive["Array"][19]
        headers = {
            name: cached[name]
            for name in (
                "Authorization",
                "X-Apple-Store-Front",
                "X-Apple-Client-Application",
                "User-Agent",
                "Accept-Language",
            )
            if cached.get(name)
        }
    except (KeyError, IndexError, TypeError, plistlib.InvalidFileException) as exc:
        raise AppleAuthorizationError(
            "Podcasts authorization cache format was not recognized"
        ) from exc

    authorization = headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise AppleAuthorizationError("Podcasts cache has no bearer authorization")
    if _jwt_expired(authorization.removeprefix("Bearer ")):
        raise AppleAuthorizationError("Podcasts bearer authorization has expired")
    headers["Origin"] = "https://podcasts.apple.com"
    return headers


def _jwt_expired(token: str) -> bool:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        expiry = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        return float(expiry) <= time.time() + 30
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return True
