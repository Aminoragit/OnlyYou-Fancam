import os
import sys
import subprocess
import re
from typing import Callable, Optional, Dict, Any
from core.config import FFMPEG_EXE, STORAGE_DIR

def is_youtube_url(text: str) -> bool:
    """Check if the given string is a YouTube URL."""
    if not text:
        return False
    text = text.strip()
    youtube_patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
        r'youtu\.be\/[a-zA-Z0-9_-]+',
        r'youtube\.com\/watch\?v=[a-zA-Z0-9_-]+',
        r'youtube\.com\/shorts\/[a-zA-Z0-9_-]+',
    ]
    return any(re.search(pat, text, re.IGNORECASE) for pat in youtube_patterns)

def ensure_yt_dlp() -> bool:
    """Ensure yt-dlp is installed, or install it automatically via pip."""
    try:
        import yt_dlp
        return True
    except ImportError:
        print("[Downloader] yt-dlp not found. Installing yt-dlp automatically...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", "yt-dlp"]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("[Downloader] yt-dlp installed successfully.")
            return True
        except Exception as e:
            print(f"[Downloader] Failed to auto-install yt-dlp: {e}")
            return False

def download_youtube_video(
    url: str,
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    start_sec: Optional[float] = None,
    end_sec: Optional[float] = None
) -> Dict[str, Any]:
    """
    Download a video from YouTube using yt-dlp.
    Optionally clips between start_sec and end_sec.
    Returns:
        dict: {'success': bool, 'filepath': str, 'title': str, 'error': str}
    """
    if not ensure_yt_dlp():
        return {'success': False, 'filepath': '', 'title': '', 'error': 'Failed to install/load yt-dlp.'}

    import yt_dlp

    if not output_dir:
        output_dir = os.path.join(STORAGE_DIR, "downloads")
    os.makedirs(output_dir, exist_ok=True)

    outtmpl = os.path.join(output_dir, "%(title)s_%(id)s.%(ext)s")

    def _progress_hook(d):
        if progress_callback and d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            percent = (downloaded / total * 100) if total > 0 else 0.0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            progress_callback({
                'status': 'downloading',
                'percent': round(percent, 1),
                'downloaded_bytes': downloaded,
                'total_bytes': total,
                'speed': speed,
                'eta': eta,
                'filename': d.get('filename', '')
            })
        elif progress_callback and d.get('status') == 'finished':
            progress_callback({
                'status': 'finished',
                'percent': 100.0,
                'filename': d.get('filename', '')
            })

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': outtmpl,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'progress_hooks': [_progress_hook],
        'ffmpeg_location': FFMPEG_EXE,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    if start_sec is not None or end_sec is not None:
        s = start_sec if start_sec is not None else 0
        ydl_opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [(s, end_sec)])
        ydl_opts['force_keyframes_at_cuts'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Check for possible .mp4 merge
            base, _ = os.path.splitext(filename)
            mp4_file = base + ".mp4"
            if os.path.exists(mp4_file):
                final_path = mp4_file
            elif os.path.exists(filename):
                final_path = filename
            else:
                final_path = filename

            return {
                'success': True,
                'filepath': os.path.abspath(final_path),
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'error': None
            }
    except Exception as e:
        return {
            'success': False,
            'filepath': '',
            'title': '',
            'error': str(e)
        }
