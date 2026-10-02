import logging
import subprocess
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

def generate_audio_stream(video_id: str):
    """
    Mengambil audio stream langsung dari YouTube menggunakan yt-dlp stdout pipe.
    """
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Menjalankan yt-dlp sebagai subprocess untuk pipe audio byte secara langsung
    cmd = [
        "yt-dlp",
        "-f", "ba/ba*", # Ambil best audio
        "-o", "-",      # Output ke stdout (pipe)
        "--no-playlist",
        "--quiet",
        youtube_url
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Generator function untuk mengirimkan chunk audio secara berurutan
        def iterfile():
            while True:
                data = process.stdout.read(4096 * 8) # Read 32KB chunk
                if not data:
                    break
                yield data
            process.stdout.close()
            process.wait()

        return StreamingResponse(iterfile(), media_type="audio/mpeg")
    except Exception as e:
        logger.error("Error piping stream for %s: %s", video_id, e)
        return None