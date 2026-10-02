import logging
import requests
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Daftar instance Invidious API
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us"
]

# Daftar instance Piped API
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.privacydev.net",
    "https://piped-api.garudalinux.org"
]

def get_stream_from_invidious(video_id: str) -> str:
    """Mengekstrak stream URL via Invidious API"""
    for instance in INVIDIOUS_INSTANCES:
        try:
            url = f"{instance}/api/v1/videos/{video_id}"
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                adaptive_formats = data.get("adaptiveFormats", [])
                
                # Filter format audio
                audio_formats = [f for f in adaptive_formats if f.get("type", "").startswith("audio/")]
                if audio_formats:
                    # Urutkan berdasarkan bitrate tertinggi
                    best_audio = sorted(audio_formats, key=lambda x: int(x.get("bitrate", 0)), reverse=True)[0]
                    return best_audio.get("url")
        except Exception as err:
            logger.warning("Invidious instance %s error: %s", instance, err)
            continue
    return None

def get_stream_from_piped(video_id: str) -> str:
    """Mengekstrak stream URL via Piped API"""
    for instance in PIPED_INSTANCES:
        try:
            url = f"{instance}/streams/{video_id}"
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                audio_streams = data.get("audioStreams", [])
                if audio_streams:
                    best_audio = sorted(audio_streams, key=lambda x: x.get("bitrate", 0), reverse=True)[0]
                    return best_audio.get("url")
        except Exception as err:
            logger.warning("Piped instance %s error: %s", instance, err)
            continue
    return None

def get_stream_from_cobalt(video_id: str) -> str:
    """Fallback ke Cobalt API jika Invidious & Piped gagal"""
    try:
        url = "https://api.cobalt.tools/"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "downloadMode": "audio",
            "audioFormat": "mp3"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            return data.get("url")
    except Exception as err:
        logger.warning("Cobalt API error: %s", err)
    return None

def get_direct_stream_url(video_id: str) -> str:
    """Fungsi pembantu dengan fallback bertahap"""
    # 1. Coba Invidious
    stream_url = get_stream_from_invidious(video_id)
    if stream_url:
        logger.info("Stream berhasil ditemukan via Invidious")
        return stream_url

    # 2. Coba Piped
    stream_url = get_stream_from_piped(video_id)
    if stream_url:
        logger.info("Stream berhasil ditemukan via Piped")
        return stream_url

    # 3. Coba Cobalt
    stream_url = get_stream_from_cobalt(video_id)
    if stream_url:
        logger.info("Stream berhasil ditemukan via Cobalt")
        return stream_url

    return None

def generate_audio_stream(video_id: str):
    """Mem-pipe audio stream ke client"""
    direct_url = get_direct_stream_url(video_id)
    
    if not direct_url:
        logger.error("Semua provider (Invidious/Piped/Cobalt) gagal untuk video_id: %s", video_id)
        raise HTTPException(
            status_code=404, 
            detail="Gagal mengekstrak stream audio dari semua provider backend"
        )

    try:
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        r = requests.get(direct_url, headers=req_headers, stream=True, timeout=15)

        def iterfile():
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    yield chunk

        content_type = r.headers.get('Content-Type', 'audio/mpeg')
        return StreamingResponse(iterfile(), media_type=content_type)

    except Exception as e:
        logger.error("Error piping audio stream for %s: %s", video_id, e)
        raise HTTPException(status_code=500, detail=f"Gagal melakukan stream audio: {str(e)}")