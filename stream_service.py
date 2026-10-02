import logging
import yt_dlp

logger = logging.getLogger(__name__)

def get_stream_url(video_id: str) -> str:
    """
    Mengambil direct URL stream audio berdasarkan YouTube Video ID menggunakan yt-dlp.
    Dioptimalkan untuk lingkungan Serverless Vercel.
    """
    ydl_opts = {
        # Utamakan format audio m4a atau webm yang ringan dan kompatibel dengan Mobile (React Native)
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        # Gunakan User-Agent browser asli agar tidak gampang di-block oleh YouTube Bot Detection
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if not info:
                logger.error("No info extracted for video_id: %s", video_id)
                return None
            
            # Jika info berbentuk playlist/entries, ambil entry pertama
            if 'entries' in info and len(info['entries']) > 0:
                info = info['entries'][0]

            stream_url = info.get('url')
            return stream_url
    except Exception as e:
        logger.error("Error extracting stream URL for %s: %s", video_id, e)
        return None