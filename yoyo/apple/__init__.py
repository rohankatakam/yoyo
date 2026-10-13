"""Apple catalog + existing TTML only. No audio/transcription submission."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
from .auth import local_podcasts_headers
from ..artifacts import store_bytes
from ..budget import timeout
from ..resolution.cache import Cache

AMP = "https://amp-api.podcasts.apple.com/v1/catalog"
TTML = (
    Path.home()
    / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML"
)


class TranscriptUnavailable(RuntimeError):
    pass


def episode_id(reference):
    if str(reference).isdigit():
        return str(reference)
    url = urlparse(reference)
    value = parse_qs(url.query).get("i", [""])[0]
    if (
        url.scheme != "https"
        or url.hostname != "podcasts.apple.com"
        or not value.isdigit()
    ):
        raise ValueError("Use an Apple episode URL containing ?i=episode-id")
    return value


def request(url, params=None, *, authorized=False, binary=False, refresh=""):
    if authorized and urlparse(url).hostname != "amp-api.podcasts.apple.com":
        raise ValueError("Apple credentials may only be sent to the Apple catalog")

    def execute():
        response = httpx.get(
            url,
            params=params,
            headers=local_podcasts_headers() if authorized else {},
            timeout=timeout(60),
            follow_redirects=False,
        )
        if response.status_code == 404 and "/transcripts" in url:
            return {"http_status": 404, "data": []}
        response.raise_for_status()
        return (
            {"artifact": store_bytes(response.content, "ttml")}
            if binary
            else response.json()
        )

    return Cache().call(
        "apple-transcript" if binary else "apple-catalog",
        {"url": url, "params": params, "refresh": refresh},
        execute,
    )


def normalize_item(item):
    if "attributes" in item:
        a = item["attributes"]
        shows = item.get("relationships", {}).get("podcast", {}).get("data", [])
        show = shows[0].get("attributes", {}) if shows else {}
        return {
            "episodeId": str(item["id"]),
            "title": a.get("name"),
            "description": a.get("fullDescription")
            or a.get("description", {}).get("standard"),
            "itunesUrl": a.get("url"),
            "releaseDate": a.get("releaseDateTime"),
            "durationSeconds": (a.get("durationInMilliseconds") or 0) / 1000,
            "podcast": show.get("name"),
            "feedUrl": show.get("feedUrl"),
        }
    return {
        "episodeId": str(item["trackId"]),
        "title": item.get("trackName"),
        "description": item.get("description"),
        "itunesUrl": item.get("trackViewUrl"),
        "releaseDate": item.get("releaseDate"),
        "durationSeconds": (item.get("trackTimeMillis") or 0) / 1000,
        "podcast": item.get("collectionName"),
        "feedUrl": item.get("feedUrl"),
    }


def metadata(reference, country="us"):
    eid = episode_id(reference)
    show = re.search(r"/id(\d+)", reference)
    if show:
        data = request(
            "https://itunes.apple.com/lookup",
            {
                "id": show[1],
                "entity": "podcastEpisode",
                "limit": 200,
                "country": country,
            },
        )
        for item in data.get("results", []):
            if str(item.get("trackId")) == eid:
                return normalize_item(item)
    data = request(
        f"{AMP}/{country}/podcast-episodes/{eid}",
        {"extend": "fullDescription", "include": "podcast", "l": "en-US"},
        authorized=True,
    )
    if not data.get("data"):
        raise ValueError("Episode not found in Apple catalog")
    return normalize_item(data["data"][0])


def transcript(eid, country="us"):
    cached = next(
        (p for p in TTML.glob(f"**/transcript_{eid}.ttml*") if p.is_file()), None
    )
    if cached:
        return store_bytes(cached.read_bytes(), "ttml")
    data = request(
        f"{AMP}/{country}/podcast-episodes/{eid}/transcripts",
        {
            "fields": "ttmlToken,ttmlAssetUrls,primaryLanguageTag",
            "l": "en-US",
            "with": "entitlements",
        },
        authorized=True,
    )
    rows = data.get("data") or []
    url = (
        rows[0].get("attributes", {}).get("ttmlAssetUrls", {}).get("ttml")
        if rows
        else None
    )
    if not url:
        raise TranscriptUnavailable(f"No existing Apple transcript for {eid}")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".apple.com"):
        raise ValueError("Unexpected Apple transcript asset host")
    return request(url, binary=True)["artifact"]


def search(query, limit=10, country="us", refresh=""):
    if not query.strip() or not 1 <= limit <= 25:
        raise ValueError("Search needs a query and limit 1–25")
    data = request(
        "https://itunes.apple.com/search",
        {
            "term": query,
            "media": "podcast",
            "entity": "podcastEpisode",
            "limit": limit,
            "country": country,
        },
        refresh=refresh,
    )
    return [
        normalize_item(i)
        for i in data.get("results", [])
        if i.get("wrapperType") == "podcastEpisode"
    ]
