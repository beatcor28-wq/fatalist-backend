import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from spotify_service import import_spotify_playlist
from stream_service import get_stream_url
from ytmusic_service import get_playlist_tracks, get_related_tracks, get_track_lyrics, get_trending_playlists, search_tracks


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fatalist API",
    description="Backend API untuk Aplikasi Streaming Musik Fatalist",
    version="1.0.0",
)

# Tambahkan CORS Middleware agar aplikasi React Native dapat mengakses API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpotifyPlaylistImport(BaseModel):
    playlist_url: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "Fatalist API",
        "message": "Welcome to Fatalist Streaming Service Backend",
    }

@app.get("/api/search")
def search(query: str = Query(..., description="Kata kunci pencarian lagu/artis")):
    results = search_tracks(query)
    return {"query": query, "count": len(results), "data": results}

@app.get("/api/lyrics/{video_id}")
def lyrics(video_id: str):
    return {"data": get_track_lyrics(video_id)}

@app.get("/api/related/{video_id}")
def related_tracks(video_id: str):
    return {"data": get_related_tracks(video_id)}

@app.get("/api/playlists/trending")
def trending_playlists():
    return {"data": get_trending_playlists()}

@app.get("/api/playlists/youtube/{playlist_id}")
def youtube_playlist(playlist_id: str):
    playlist = get_playlist_tracks(playlist_id)
    if not playlist["tracks"]:
        raise HTTPException(status_code=404, detail="Playlist YouTube Music tidak dapat dimuat.")
    return {"data": playlist}

@app.post("/api/playlists/import/spotify")
def import_playlist_from_spotify(payload: SpotifyPlaylistImport):
    try:
        return {"data": import_spotify_playlist(payload.playlist_url)}
    except ValueError as error:
        logger.warning("Spotify playlist import rejected: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Playlist Spotify tidak dapat diimpor.") from error

@app.get("/api/stream/{video_id}")
def stream(video_id: str):
    url = get_stream_url(video_id)
    if not url:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"video_id": video_id, "stream_url": url}