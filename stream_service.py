import logging
import requests
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Instance Piped & Invidious resmi yang online dan aktif
WORKING_INSTANCES = [
    {"type": "piped", "url": "https://pipedapi.kavin.rocks"},
    {"type": "piped", "url": "https://pipedapi.r33.io"},
    {"type": "piped", "url": "https://api.piped.projectsegfau.lt"},
    {"type": "invidious", "url": "https://inv.tux.pizza"},
    {"type": "invidious", "url": "https://invidious.nerdvpn.de"},
]

def fetch_stream_url(video_id: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    for instance in WORKING_INSTANCES:
        i_type = instance["type"]
        i_url = instance["url"]
        
        try:
            if i_type == "piped":
                endpoint = f"{i_url}/streams/{video_id}"
                res = requests.get(endpoint, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    audio_streams = data.get("audioStreams", [])
                    if audio_streams:
                        best = sorted(audio_streams, key=lambda x: x.get("bitrate", 0), reverse=True)[0]
                        logger.info(f"Berhasil via Piped ({i_url})")
                        return best.get("url")

            elif i_type == "invidious":
                endpoint = f"{i_url}/api/v1/videos/{video_id}"
                res = requests.get(endpoint, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    formats = [f for f in data.get("adaptiveFormats", []) if f.get("type", "").startswith("audio/")]
                    if formats:
                        best = sorted(formats, key=lambda x: int(x.get("bitrate", 0)), reverse=True)[0]
                        logger.info(f"Berhasil via Invidious ({i_url})")
                        return best.get("url")

        except Exception as err:
            logger.warning(f"Failed to fetch from {i_url}: {err}")
            continue

    # Fallback Terakhir: Cobalt Tools API
    try:
        cobalt_res = requests.post(
            "https://api.cobalt.tools/",
            json={"url": f"https://www.youtube.com/watch?v={video_id}", "downloadMode": "audio"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=8
        )
        if cobalt_res.status_code == 200:
            logger.info("Berhasil via Cobalt API")
            return cobalt_res.json().get("url")
    except Exception as err:
        logger.warning(f"Failed Cobalt API: {err}")

    return None

def generate_audio_stream(video_id: str):
    direct_url = fetch_stream_url(video_id)
    
    if not direct_url:
        logger.error(f"Semua provider stream gagal untuk video_id: {video_id}")
        raise HTTPException(status_code=404, detail="Audio stream unavailable across all providers")

    try:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = requests.get(direct_url, headers=req_headers, stream=True, timeout=15)

        def iterfile():
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    yield chunk

        content_type = r.headers.get("Content-Type", "audio/mpeg")
        return StreamingResponse(iterfile(), media_type=content_type)

    except Exception as e:
        logger.error(f"Error streaming audio for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")