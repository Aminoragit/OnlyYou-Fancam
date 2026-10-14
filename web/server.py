import os
import sys
import json
import shutil
import asyncio
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import BASE_DIR, STORAGE_DIR, JOBS_DIR
from core.downloader import is_youtube_url, download_youtube_video
from core.pipeline import FancamJob, FancamPipeline

app = FastAPI(title="AutoFancam Local", version="3.0")

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Mount static files
static_dir = os.path.join(BASE_DIR, "web", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

pipeline = FancamPipeline()
active_jobs: dict[str, FancamJob] = {}

class StartPathRequest(BaseModel):
    file_path: str

class StartYouTubeRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>AutoFancam Local</h1><p>Static UI loading...</p>")

@app.get("/api/jobs/latest")
async def get_latest_job():
    if not os.path.exists(JOBS_DIR):
        raise HTTPException(status_code=404, detail="No jobs found")
    subdirs = [os.path.join(JOBS_DIR, d) for d in os.listdir(JOBS_DIR) if os.path.isdir(os.path.join(JOBS_DIR, d))]
    subdirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for sdir in subdirs:
        mpath = os.path.join(sdir, "preview", "preview_manifest_v1.json")
        if os.path.exists(mpath):
            jid = os.path.basename(sdir)
            return {"job_id": jid}
    raise HTTPException(status_code=404, detail="No valid jobs found")

@app.post("/api/demo/start")
async def start_demo_job():
    demo_path = os.path.join(STORAGE_DIR, "test_data", "nmixx_dice_test.mp4")
    if not os.path.isfile(demo_path):
        demo_path = os.path.join(STORAGE_DIR, "test_data", "dancers.mp4")
    if not os.path.isfile(demo_path):
        raise HTTPException(status_code=404, detail="Demo video not found on disk")
    job = FancamJob(source_path=os.path.abspath(demo_path))
    active_jobs[job.job_id] = job
    pipeline.run_job_async(job)
    return {"success": True, "job_id": job.job_id, "source_path": demo_path}

@app.post("/api/jobs/start-path")
async def start_job_by_path(req: StartPathRequest):
    path = req.file_path.strip().strip('"').strip("'")
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"File does not exist: {path}")

    job = FancamJob(source_path=path)
    active_jobs[job.job_id] = job
    pipeline.run_job_async(job)
    return {"success": True, "job_id": job.job_id, "source_path": path}

@app.post("/api/jobs/upload")
async def upload_video(file: UploadFile = File(...)):
    upload_dir = os.path.join(STORAGE_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    dest_path = os.path.join(upload_dir, file.filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job = FancamJob(source_path=dest_path)
    active_jobs[job.job_id] = job
    pipeline.run_job_async(job)
    return {"success": True, "job_id": job.job_id, "source_path": dest_path}

@app.post("/api/jobs/start-youtube")
async def start_job_by_youtube(req: StartYouTubeRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    # Create placeholder job
    job = FancamJob(source_path="")
    job.progress_msg = "Preparing to download video with yt-dlp..."
    job.preview_state = "DOWNLOADING"
    active_jobs[job.job_id] = job

    def _download_and_start(job_obj: FancamJob, yt_url: str):
        def _prog(d):
            pct = d.get('percent', 0.0)
            job_obj.progress_msg = f"Downloading YouTube video ({pct}%)..."
            job_obj.fast_lane_percent = round(pct * 0.2, 1) # first 20%
            job_obj.emit_update()

        dl_res = download_youtube_video(yt_url, progress_callback=_prog)
        if not dl_res['success']:
            job_obj.error = dl_res['error']
            job_obj.preview_state = "FAILED"
            job_obj.progress_msg = f"Download error: {dl_res['error']}"
            job_obj.emit_update()
            return

        job_obj.source_path = dl_res['filepath']
        job_obj.progress_msg = f"Downloaded '{dl_res['title']}'. Starting analysis..."
        job_obj.emit_update()
        pipeline.run_job_async(job_obj)

    background_tasks.add_task(_download_and_start, job, url)
    return {"success": True, "job_id": job.job_id, "message": "Download started in background."}

@app.get("/api/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    job = active_jobs.get(job_id)
    if not job:
        # Try loading manifest from disk
        manifest_path = os.path.join(JOBS_DIR, job_id, "preview", "preview_manifest_v1.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return JSONResponse(json.load(f))
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(job.to_dict())

@app.get("/api/jobs/{job_id}/posters/{filename}")
async def get_poster(job_id: str, filename: str):
    poster_path = os.path.join(JOBS_DIR, job_id, "preview", "posters", filename)
    if os.path.exists(poster_path):
        return FileResponse(poster_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Poster not found")

@app.get("/api/jobs/{job_id}/exports/{filename}")
async def get_export_file(job_id: str, filename: str):
    file_path = os.path.join(JOBS_DIR, job_id, "export", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4", filename=filename)
    raise HTTPException(status_code=404, detail="Export file not found")

@app.get("/api/jobs/{job_id}/source-video")
async def stream_source_video(job_id: str):
    """Serve source video with HTTP range support for smooth HTML5 seeking."""
    job = active_jobs.get(job_id)
    if not job or not os.path.isfile(job.source_path):
        # Look in jobs dir manifest
        manifest_path = os.path.join(JOBS_DIR, job_id, "preview", "preview_manifest_v1.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                src = data.get("source_path")
                if src and os.path.isfile(src):
                    return FileResponse(src, media_type="video/mp4")
        raise HTTPException(status_code=404, detail="Source video not found")

    return FileResponse(job.source_path, media_type="video/mp4")

@app.get("/api/jobs/{job_id}/qa-report")
async def get_qa_report(job_id: str):
    qa_path = os.path.join(JOBS_DIR, job_id, "qa", "qa_report.json")
    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    raise HTTPException(status_code=404, detail="QA report not found")
