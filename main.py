import os
import sys
import argparse
import webbrowser
import threading
import time
import uvicorn

from core.config import FFMPEG_EXE, YOLO_MODEL_PATH
from core.downloader import ensure_yt_dlp, is_youtube_url, download_youtube_video
from core.pipeline import FancamJob, FancamPipeline

def parse_args():
    parser = argparse.ArgumentParser(description="AutoFancam Local — AI Fancam Generator")
    parser.add_argument("--video", type=str, help="Path to local video file to process directly")
    parser.add_argument("--youtube", type=str, help="YouTube URL to download and process directly")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for web server")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    return parser.parse_args()

def open_browser_delayed(url: str, delay: float = 1.2):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    args = parse_args()

    print("=" * 65)
    print("  AutoFancam Local — AI 가상 직캠 및 자동 MP4 생성기 v3.0")
    print("=" * 65)
    print(f"[System] Python: {sys.version.split()[0]}")
    print(f"[System] FFmpeg: {FFMPEG_EXE}")
    print(f"[System] YOLO Model: {YOLO_MODEL_PATH}")

    # Ensure yt-dlp is available
    ensure_yt_dlp()

    pipeline = FancamPipeline()

    # Direct CLI processing if argument provided
    if args.video or args.youtube:
        target_path = None
        if args.youtube:
            print(f"[CLI] Downloading YouTube video: {args.youtube}")
            res = download_youtube_video(args.youtube)
            if not res['success']:
                print(f"[CLI Error] YouTube download failed: {res['error']}")
                sys.exit(1)
            target_path = res['filepath']
        else:
            target_path = os.path.abspath(args.video)

        if not os.path.isfile(target_path):
            print(f"[CLI Error] Video file not found: {target_path}")
            sys.exit(1)

        print(f"[CLI] Processing video: {target_path}")
        job = FancamJob(source_path=target_path)

        def _print_status(status):
            msg = status.get('progress_msg', '')
            fl_pct = status.get('fast_lane_percent', 0)
            ex_pct = status.get('export_percent', 0)
            print(f"\r[{status.get('preview_state')}/{status.get('export_state')}] FL: {fl_pct}% | EX: {ex_pct}% | {msg[:50]}", end="")

        job.add_listener(_print_status)
        pipeline._run_pipeline(job)
        print("\n[CLI] Processing complete!")
        print(f"[CLI] Output Directory: {job.job_dir}")
        return

    # Web Studio Mode
    url = f"http://{args.host}:{args.port}"
    print(f"\n[Web Studio] 서버 시작: {url}")
    print("[Web Studio] 브라우저가 자동으로 열립니다. (종료: Ctrl+C)\n")

    if not args.no_browser:
        threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()

    from web.server import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
