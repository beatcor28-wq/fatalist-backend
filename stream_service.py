import logging
import requests
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Daftar instance Piped API publik sebagai fallback
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.privacydev.net",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.mha.fi"
]

def get_direct_stream_url(video_id: str) -> str:
    """
    Mengambil direct audio URL dari Piped API instance.
    """
    for instance in PIPED_INSTANCES:
        try:
            url = f"{instance}/streams/{video_id}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                audio_streams = data.get("audioStreams", [])
                if audio_streams:
                    # Ambil stream audio dengan bit rate / kualitas terbaik
                    best_audio = sorted(audio_streams, key=lambda x: x.get("bitrate", 0), reverse=True)[0]
                    return best_audio.get("url")
        except Exception as err:
            logger.warning("Gagal mengambil stream dari instance %s: %s", instance, err)
            continue
    return None

def generate_audio_stream(video_id: str):
    """
    Mendapatkan direct audio URL dan mem-pipe stream data ke client.
    """
    direct_url = get_direct_stream_url(video_id)
    
    if not direct_url:
        logger.error("Gagal mendapatkan stream URL untuk video_id: %s dari semua instance", video_id)
        raise HTTPException(status_code=404, detail="Audio stream not found or blocked by YouTube")

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