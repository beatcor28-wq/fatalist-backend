from ytmusicapi import YTMusic

# Inisialisasi client YTMusic
ytmusic = YTMusic()


def normalize_track(item: dict):
    thumbnails = item.get("thumbnails") or item.get("thumbnail") or []
    artwork = max(
        thumbnails,
        key=lambda thumbnail: thumbnail.get("width", 0) * thumbnail.get("height", 0),
        default={},
    )
    artwork_fallback = artwork.get("url", "")
    artwork_url = artwork_fallback
    if "=" in artwork_fallback and "googleusercontent.com" in artwork_fallback:
        artwork_url = f"{artwork_fallback.split('=')[0]}=w1200-h1200-l90-rj"

    return {
        "id": item.get("videoId"),
        "title": item.get("title"),
        "artist": ", ".join(artist["name"] for artist in item.get("artists", []) if artist.get("name")),
        "album": item.get("album", {}).get("name", "") if item.get("album") else "",
        "duration": item.get("duration") or item.get("length") or "0:00",
        "artwork": artwork_url,
        "artworkFallback": artwork_fallback,
    }


def search_tracks(query: str, limit: int = 10):
    """
    Mencari lagu di YouTube Music berdasarkan kata kunci.
    """
    try:
        results = ytmusic.search(query=query, filter="songs", limit=limit)
        cleaned_results = [normalize_track(item) for item in results if item.get("videoId")]
        if cleaned_results:
            return cleaned_results

        # Catalog entries sometimes do not appear in the strict songs filter.
        fallback_results = ytmusic.search(query=query, limit=limit)
        return [normalize_track(item) for item in fallback_results if item.get("videoId")]
    except Exception as e:
        print(f"Error searching tracks: {e}")
        return []


def get_track_lyrics(video_id: str):
    """Fetch timed lyrics when YouTube Music provides them for a track."""
    try:
        watch_playlist = ytmusic.get_watch_playlist(videoId=video_id, limit=1)
        lyrics_id = watch_playlist.get("lyrics")
        if not lyrics_id:
            return []

        result = ytmusic.get_lyrics(lyrics_id, timestamps=True)
        if not result:
            return []

        timed_lyrics = result.get("lyrics", [])
        if result.get("hasTimestamps") and isinstance(timed_lyrics, list):
            return [
                {"time": line.start_time / 1000, "text": line.text}
                for line in timed_lyrics
                if line.text.strip()
            ]

        if isinstance(timed_lyrics, str):
            return [
                {"time": index * 3, "text": line}
                for index, line in enumerate(timed_lyrics.splitlines())
                if line.strip()
            ]
    except Exception as error:
        print(f"Error fetching lyrics: {error}")

    return []


def get_related_tracks(video_id: str, limit: int = 12):
    """Build a song radio so the next track retains the current musical context."""
    try:
        radio = ytmusic.get_watch_playlist(videoId=video_id, radio=True, limit=limit)
        tracks = [normalize_track(item) for item in radio.get("tracks", [])]
        return [track for track in tracks if track.get("id") and track["id"] != video_id]
    except Exception as error:
        print(f"Error fetching related tracks: {error}")
        return []


def _normalize_playlist(item: dict, country: str) -> dict:
    thumbnails = item.get("thumbnails") or []
    artwork = max(
        thumbnails,
        key=lambda thumbnail: thumbnail.get("width", 0) * thumbnail.get("height", 0),
        default={},
    )
    return {
        "id": item.get("playlistId"),
        "title": item.get("title") or "YouTube Music Charts",
        "country": country,
        "artwork": artwork.get("url", ""),
    }


def get_trending_playlists(limit: int = 6):
    """Return public playlists from the current YouTube Music charts."""
    playlists = []
    seen_ids = set()
    for country in ("ID", "ZZ", "US"):
        try:
            charts = ytmusic.get_charts(country=country)
            for category in ("videos", "genres", "daily", "weekly"):
                for item in charts.get(category, []):
                    playlist = _normalize_playlist(item, country)
                    playlist_id = playlist["id"]
                    if playlist_id and playlist_id not in seen_ids:
                        seen_ids.add(playlist_id)
                        playlists.append(playlist)
                    if len(playlists) >= limit:
                        return playlists
        except Exception as error:
            print(f"Error fetching YouTube Music charts for {country}: {error}")
    return playlists


def get_playlist_tracks(playlist_id: str, limit: int = 50):
    try:
        playlist = ytmusic.get_playlist(playlist_id, limit=limit)
        tracks = [normalize_track(item) for item in playlist.get("tracks", []) if item.get("videoId")]
        return {
            "name": playlist.get("title") or "YouTube Music Charts",
            "tracks": tracks,
        }
    except Exception as error:
        print(f"Error fetching YouTube Music playlist {playlist_id}: {error}")
        return {"name": "YouTube Music Charts", "tracks": []}
