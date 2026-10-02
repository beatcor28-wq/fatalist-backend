import logging
import requests
import yt_dlp
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

def generate_audio_stream(video_id: str):
    """
    Mengekstrak direct URL audio menggunakan yt-dlp dengan multiple fallback client,
    lalu mem-pipe/proxy byte stream-nya secara langsung ke client.
    """
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        # Kombinasi client terbaik untuk melewati IP datacenter/serverless block
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'tv_embedded'],
                'skip': ['webpage', 'configs'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        # 1. Dapatkan direct media URL dari yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if not info:
                logger.error("yt-dlp gagal mengekstrak info untuk video_id: %s", video_id)
                raise HTTPException(status_code=404, detail="Audio info not found")
            
            if 'entries' in info and len(info['entries']) > 0:
                info = info['entries'][0]

            direct_url = info.get('url')

        if not direct_url:
            raise HTTPException(status_code=404, detail="Direct stream URL not found")

        # 2. Request stream data dari direct URL dengan stream=True
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15',
        }
        r = requests.get(direct_url, headers=req_headers, stream=True, timeout=20)

        # 3. Stream byte data langsung ke FastAPI StreamingResponse
        def iterfile():
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    yield chunk

        content_type = r.headers.get('Content-Type', 'audio/mpeg')
        return StreamingResponse(iterfile(), media_type=content_type)

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error("Error piping audio stream for %s: %s", video_id, e)
        raise HTTPException(status_code=500, detail=f"Gagal melakukan stream audio: {str(e)}")