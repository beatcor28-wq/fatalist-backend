import json
import logging
import re
from html.parser import HTMLParser

import requests

from ytmusic_service import search_tracks


SPOTIFY_EMBED_URL = "https://open.spotify.com/embed/playlist/{playlist_id}"
SPOTIFY_EMBED_HEADERS = {
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; FatalistPlaylistImporter/1.0)",
}
logger = logging.getLogger(__name__)


class _SpotifyEmbedParser(HTMLParser):
    """Collect metadata and JSON hydration payloads from Spotify's embed page."""

    def __init__(self) -> None:
        super().__init__()
        self.playlist_name: str | None = None
        self.json_scripts: list[str] = []
        self._script_attributes: dict[str, str] | None = None
        self._script_parts: list[str] = []
        self._inside_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta" and attributes.get("property") in {"og:title", "twitter:title"}:
            self.playlist_name = attributes.get("content") or self.playlist_name
        if tag == "meta" and attributes.get("name") == "title":
            self.playlist_name = attributes.get("content") or self.playlist_name
        if tag == "title":
            self._inside_title = True
            self._title_parts = []
        if tag == "script":
            self._script_attributes = attributes
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)
        if self._script_attributes is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._inside_title = False
            title = "".join(self._title_parts).strip()
            self.playlist_name = self.playlist_name or title
            self._title_parts = []
        if tag != "script" or self._script_attributes is None:
            return

        script = "".join(self._script_parts).strip()
        script_type = self._script_attributes.get("type", "").lower()
        script_id = self._script_attributes.get("id", "")
        if script and (script_id == "__NEXT_DATA__" or "json" in script_type):
            self.json_scripts.append(script)
        self._script_attributes = None
        self._script_parts = []


def get_playlist_id(playlist_url: str) -> str | None:
    if not playlist_url:
        return None
    match = re.search(r"(?:playlist[/:])([A-Za-z0-9]+)", playlist_url.strip())
    return match.group(1) if match else None


def _artist_names(track: dict) -> str:
    artists = track.get("artists") or track.get("artist") or []
    if isinstance(artists, dict):
        artists = artists.get("items") or artists.get("artists") or [artists]
    if isinstance(artists, list):
        names = [artist.get("name", "") for artist in artists if isinstance(artist, dict)]
        result = ", ".join(name for name in names if name)
        if result:
            return result
    for field in ("artistName", "artistNames", "subtitle"):
        value = track.get(field)
        if isinstance(value, str) and value:
            return value
    return ""


def _iter_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _extract_tracks(payloads: list[object]) -> list[tuple[str, str]]:
    tracks: list[tuple[str, str]] = []
    seen_uris: set[str] = set()

    for payload in payloads:
        for item in _iter_dicts(payload):
            track = item.get("track") if isinstance(item.get("track"), dict) else item
            uri = track.get("uri") or track.get("id")
            is_track = isinstance(uri, str) and uri.startswith("spotify:track:")
            if not is_track:
                continue

            title = track.get("name") or track.get("title")
            if not isinstance(title, str) or not title or uri in seen_uris:
                continue

            seen_uris.add(uri)
            tracks.append((title, _artist_names(track)))

    return tracks


def _extract_playlist_name(payloads: list[object]) -> str | None:
    for payload in payloads:
        for item in _iter_dicts(payload):
            uri = item.get("uri") or item.get("id")
            name = item.get("name") or item.get("title")
            if (
                isinstance(uri, str)
                and uri.startswith("spotify:playlist:")
                and isinstance(name, str)
                and name
            ):
                return name
    return None


def _clean_playlist_name(name: str | None, fallback: str) -> str:
    if not name:
        return fallback
    return re.sub(r"\s+on Spotify$", "", name, flags=re.IGNORECASE).strip() or fallback


def scrape_spotify_embed(playlist_id: str) -> tuple[str, list[tuple[str, str]]]:
    response = requests.get(
        SPOTIFY_EMBED_URL.format(playlist_id=playlist_id),
        headers=SPOTIFY_EMBED_HEADERS,
        timeout=20,
    )
    if response.status_code == 404:
        raise ValueError("Playlist Spotify tidak ditemukan. Cek kembali URL/ID playlist.")
    if response.status_code in (401, 403):
        raise ValueError("Playlist Spotify tidak dapat dibaca. Pastikan playlist bersifat publik.")
    response.raise_for_status()

    parser = _SpotifyEmbedParser()
    parser.feed(response.text)
    parser.close()

    payloads: list[object] = []
    for script in parser.json_scripts:
        try:
            payloads.append(json.loads(script))
        except json.JSONDecodeError:
            logger.debug("Ignoring non-JSON script in Spotify embed page.")

    tracks = _extract_tracks(payloads)
    if not tracks:
        raise ValueError(
            "Playlist Spotify tidak berisi track yang dapat dibaca dari widget publik. "
            "Pastikan playlist publik dan coba lagi."
        )

    playlist_name = parser.playlist_name or _extract_playlist_name(payloads)
    return _clean_playlist_name(playlist_name, "Playlist Spotify"), tracks


def _find_ytmusic_track(title: str, artists: str) -> dict | None:
    queries = [f"{title} {artists}".strip(), title]
    seen_queries: set[str] = set()
    for query in queries:
        normalized_query = query.casefold()
        if not query or normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)
        matches = search_tracks(query, limit=3)
        for match in matches:
            if match.get("id"):
                return match
    return None


def import_spotify_playlist(playlist_url: str) -> dict:
    playlist_id = get_playlist_id(playlist_url)
    if not playlist_id:
        raise ValueError("URL playlist Spotify tidak valid.")

    playlist_name, spotify_tracks = scrape_spotify_embed(playlist_id)
    tracks = []
    unmatched_tracks = []
    seen_ids: set[str] = set()

    for title, artists in spotify_tracks:
        ytmusic_track = _find_ytmusic_track(title, artists)
        if ytmusic_track:
            track_id = ytmusic_track.get("id")
            if track_id and track_id not in seen_ids:
                seen_ids.add(track_id)
                tracks.append(ytmusic_track)
        else:
            unmatched_tracks.append(f"{title} - {artists}".strip(" -"))

    logger.info(
        "Spotify embed import matched %s of %s tracks against YouTube Music.",
        len(tracks),
        len(spotify_tracks),
    )
    if not tracks:
        preview = ", ".join(unmatched_tracks[:3]) or "tidak ada track yang dapat dibaca"
        raise ValueError(
            "Playlist Spotify berhasil dibaca, tetapi YouTube Music tidak mengembalikan hasil pencarian. "
            f"Contoh track: {preview}"
        )

    return {"name": playlist_name, "tracks": tracks}
