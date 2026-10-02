import yt_dlp

def get_stream_url(video_id: str) -> str:
    """
    Mengambil direct URL stream audio berdasarkan YouTube Video ID menggunakan yt-dlp.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            # Ambil direct audio URL dari metadata
            stream_url = info.get('url')
            return stream_url
    except Exception as e:
        print(f"Error extracting stream URL for {video_id}: {e}")
        return None