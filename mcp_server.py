#!/usr/bin/env python3
"""
OnlyYou-Fancam Model Context Protocol (MCP) Server.
Enables AI assistants (Claude Desktop, Cursor, Antigravity, Cline, ChatGPT, etc.)
to intelligently generate and manage AI fancams directly via tool calls.

Protocol: Model Context Protocol (MCP) over JSON-RPC 2.0 stdio.
Apache 2.0 Licensed.
"""

import os
import sys
import json
import traceback
import io
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import STORAGE_DIR, JOBS_DIR
from core.downloader import is_youtube_url, download_youtube_video
from core.pipeline import FancamJob, FancamPipeline
from core.media_probe import probe_video

SERVER_NAME = "onlyyou-fancam"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

def log_debug(msg: str):
    """Log debug information to stderr so stdout remains purely JSON-RPC."""
    sys.stderr.write(f"[OnlyYou-MCP] {msg}\n")
    sys.stderr.flush()

TOOLS = [
    {
        "name": "create_fancam",
        "description": "Generate high-precision 9:16 vertical fancam video(s) focusing on individual performer(s) from a local video file or YouTube URL. Uses YOLOv8 + Reid Fast Lane tracking, edge letterboxing, and cinematic camera planning.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_source": {
                    "type": "string",
                    "description": "Absolute path to a local video file (.mp4, .mov, etc.) or a YouTube video URL."
                },
                "target_person_id": {
                    "type": "string",
                    "description": "Specific performer ID to render (e.g. 'person_01'). Pass 'all' or leave blank to render fancams for all identified performers.",
                    "default": "all"
                },
                "start_sec": {
                    "type": "number",
                    "description": "Start time in seconds for YouTube clip extraction (optional)."
                },
                "end_sec": {
                    "type": "number",
                    "description": "End time in seconds for YouTube clip extraction (optional)."
                },
                "damping_speed": {
                    "type": "number",
                    "description": "Virtual camera tracking responsiveness damping factor (default: 0.12).",
                    "default": 0.12
                },
                "max_accel": {
                    "type": "number",
                    "description": "Virtual camera maximum acceleration limiter in px/s^2 (default: 25.0).",
                    "default": 25.0
                }
            },
            "required": ["video_source"]
        }
    },
    {
        "name": "inspect_performers",
        "description": "Quickly scan a stage dance video without rendering full exports. Identifies all performers on stage, estimates performer count K, confidence score, and returns keyframe timestamps and preview poster URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_source": {
                    "type": "string",
                    "description": "Absolute path to a local video file or a YouTube video URL."
                },
                "start_sec": {
                    "type": "number",
                    "description": "Optional start time in seconds."
                },
                "end_sec": {
                    "type": "number",
                    "description": "Optional end time in seconds."
                }
            },
            "required": ["video_source"]
        }
    },
    {
        "name": "get_job_status",
        "description": "Get real-time progress, QA metrics, and rendered 9:16 video download paths for an ongoing or completed fancam processing job.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID returned by create_fancam or inspect_performers."
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "list_jobs",
        "description": "List existing OnlyYou-Fancam jobs stored locally, including their status, detected performer counts, and exported MP4 files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recent jobs to return (default: 10).",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "download_youtube",
        "description": "Download a video or specific snippet from YouTube using yt-dlp to local storage for fancam generation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The YouTube video URL (standard or shorts)."
                },
                "start_sec": {
                    "type": "number",
                    "description": "Optional start time in seconds."
                },
                "end_sec": {
                    "type": "number",
                    "description": "Optional end time in seconds."
                }
            },
            "required": ["url"]
        }
    }
]

# In-memory pipeline instance
_pipeline = FancamPipeline()

def _resolve_source_path(video_source: str, start_sec: Optional[float] = None, end_sec: Optional[float] = None) -> str:
    """Resolve a video source (YouTube URL or local path) to an absolute local file path."""
    source_clean = video_source.strip().strip('"').strip("'")
    if is_youtube_url(source_clean):
        log_debug(f"Downloading YouTube video: {source_clean}")
        res = download_youtube_video(source_clean, start_sec=start_sec, end_sec=end_sec)
        if not res.get("success"):
            raise ValueError(f"Failed to download YouTube video: {res.get('error')}")
        return res["filepath"]
    
    if not os.path.isfile(source_clean):
        # Check in storage/test_data
        alt_path = os.path.join(STORAGE_DIR, "test_data", source_clean)
        if os.path.isfile(alt_path):
            return os.path.abspath(alt_path)
        raise FileNotFoundError(f"Video file not found at: {source_clean}")
    return os.path.abspath(source_clean)

def handle_create_fancam(arguments: Dict[str, Any]) -> Dict[str, Any]:
    video_source = arguments.get("video_source", "")
    target_person_id = arguments.get("target_person_id", "all")
    start_sec = arguments.get("start_sec")
    end_sec = arguments.get("end_sec")
    damping_speed = arguments.get("damping_speed", 0.12)
    max_accel = arguments.get("max_accel", 25.0)

    local_path = _resolve_source_path(video_source, start_sec, end_sec)
    log_debug(f"Resolved video path: {local_path}")

    job = FancamJob(source_path=local_path)
    
    # Run pipeline synchronously for MCP call
    log_debug(f"Starting Fancam pipeline for job {job.job_id}...")
    _pipeline._run_pipeline(job)

    if job.error:
        return {
            "success": False,
            "job_id": job.job_id,
            "error": job.error
        }

    # Filter export files if specific person requested
    exports = job.export_files
    if target_person_id and target_person_id != "all":
        exports = [e for e in exports if e.get("person_id") == target_person_id]

    qa_report = job.generate_qa_report()

    return {
        "success": True,
        "job_id": job.job_id,
        "source_path": local_path,
        "k_performers_detected": job.k_initial,
        "k_confidence": job.k_confidence,
        "identities": job.identities,
        "export_files": exports,
        "timing": job.timing,
        "qa_status": qa_report.get("overall_status"),
        "warnings": qa_report.get("warnings", [])
    }

def handle_inspect_performers(arguments: Dict[str, Any]) -> Dict[str, Any]:
    video_source = arguments.get("video_source", "")
    start_sec = arguments.get("start_sec")
    end_sec = arguments.get("end_sec")

    local_path = _resolve_source_path(video_source, start_sec, end_sec)
    probe_info = probe_video(local_path)

    job = FancamJob(source_path=local_path)
    
    # We run the Fast Lane scan & clustering
    _pipeline._run_pipeline(job)

    return {
        "success": True,
        "job_id": job.job_id,
        "source_path": local_path,
        "video_info": probe_info,
        "k_performers_detected": job.k_initial,
        "k_confidence": job.k_confidence,
        "identities": job.identities,
        "fast_lane_sec": job.timing.get("fast_lane_sec", 0.0)
    }

def handle_get_job_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    job_id = arguments.get("job_id", "").strip()
    if not job_id:
        raise ValueError("job_id is required.")

    manifest_path = os.path.join(JOBS_DIR, job_id, "preview", "preview_manifest_v1.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Job not found: {job_id}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    qa_path = os.path.join(JOBS_DIR, job_id, "qa", "qa_report.json")
    qa_data = {}
    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            qa_data = json.load(f)

    return {
        "job_id": job_id,
        "status": data.get("export_state", data.get("preview_state")),
        "progress_msg": data.get("progress_msg"),
        "fast_lane_percent": data.get("fast_lane_percent"),
        "export_percent": data.get("export_percent"),
        "k_initial": data.get("k_initial"),
        "identities": data.get("identities", []),
        "export_files": data.get("export_files", []),
        "timing": data.get("timing", {}),
        "qa_report": qa_data
    }

def handle_list_jobs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(arguments.get("limit", 10))
    if not os.path.exists(JOBS_DIR):
        return {"jobs": []}

    subdirs = [os.path.join(JOBS_DIR, d) for d in os.listdir(JOBS_DIR) if os.path.isdir(os.path.join(JOBS_DIR, d))]
    subdirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    results = []
    for sdir in subdirs[:limit]:
        mpath = os.path.join(sdir, "preview", "preview_manifest_v1.json")
        jid = os.path.basename(sdir)
        if os.path.exists(mpath):
            try:
                with open(mpath, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                results.append({
                    "job_id": jid,
                    "created_at": datetime.fromtimestamp(os.path.getmtime(mpath)).isoformat(),
                    "source_path": manifest.get("source_path"),
                    "k_performers": manifest.get("k_initial", 0),
                    "status": manifest.get("export_state", manifest.get("preview_state")),
                    "exported_count": len([e for e in manifest.get("export_files", []) if e.get("state") == "completed"])
                })
            except Exception:
                pass
        else:
            results.append({
                "job_id": jid,
                "created_at": datetime.fromtimestamp(os.path.getmtime(sdir)).isoformat(),
                "status": "INCOMPLETE"
            })

    return {"total_jobs": len(subdirs), "jobs": results}

def handle_download_youtube(arguments: Dict[str, Any]) -> Dict[str, Any]:
    url = arguments.get("url", "").strip()
    start_sec = arguments.get("start_sec")
    end_sec = arguments.get("end_sec")

    if not is_youtube_url(url):
        raise ValueError(f"Invalid YouTube URL: {url}")

    res = download_youtube_video(url, start_sec=start_sec, end_sec=end_sec)
    if not res.get("success"):
        raise ValueError(f"Download failed: {res.get('error')}")

    probe = probe_video(res["filepath"])
    return {
        "success": True,
        "title": res.get("title"),
        "filepath": res.get("filepath"),
        "probe": probe
    }

def dispatch_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the requested tool and return a JSON-serializable dictionary."""
    if name == "create_fancam":
        return handle_create_fancam(arguments)
    elif name == "inspect_performers":
        return handle_inspect_performers(arguments)
    elif name == "get_job_status":
        return handle_get_job_status(arguments)
    elif name == "list_jobs":
        return handle_list_jobs(arguments)
    elif name == "download_youtube":
        return handle_download_youtube(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

def send_response(response: Dict[str, Any]):
    """Send JSON-RPC response to stdout followed by newline."""
    body = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(body + "\n")
    sys.stdout.flush()

def handle_request(req: Dict[str, Any]):
    """Process a single JSON-RPC 2.0 request."""
    msg_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    log_debug(f"Handling method: {method} (id={msg_id})")

    if method == "initialize":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        })
    elif method == "notifications/initialized":
        # Client acknowledgement - no response needed
        log_debug("Client initialized successfully.")
    elif method == "ping":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {}
        })
    elif method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS
            }
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            tool_result = dispatch_tool(tool_name, tool_args)
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_result, ensure_ascii=False, indent=2)
                        }
                    ],
                    "isError": False
                }
            })
        except Exception as e:
            tb = traceback.format_exc()
            log_debug(f"Tool execution failed: {tb}")
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {str(e)}\n\nDetails:\n{tb}"
                        }
                    ],
                    "isError": True
                }
            })
    elif method == "resources/list":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "resources": []
            }
        })
    else:
        if msg_id is not None:
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })

def run_server():
    """Main stdio loop reading JSON-RPC requests."""
    log_debug(f"Starting {SERVER_NAME} v{SERVER_VERSION} MCP Server on stdio...")
    
    # Configure stdin/stdout for UTF-8
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            # Support Content-Length header framing if sent
            if line_str.lower().startswith("content-length:"):
                length_part = line_str.split(":", 1)[1].strip()
                content_len = int(length_part)
                # Next line might be blank separator
                next_line = sys.stdin.readline()
                if next_line.strip():
                    body = next_line + sys.stdin.read(content_len - len(next_line))
                else:
                    body = sys.stdin.read(content_len)
                req = json.loads(body)
            else:
                req = json.loads(line_str)

            handle_request(req)

        except (KeyboardInterrupt, EOFError):
            log_debug("Server shutting down.")
            break
        except json.JSONDecodeError as jde:
            log_debug(f"Invalid JSON received: {jde}")
        except Exception as e:
            log_debug(f"Unhandled loop error: {traceback.format_exc()}")

def run_self_test():
    """Run an automated self-test of the MCP server methods."""
    print("=== OnlyYou-Fancam MCP Server Self-Test ===")
    
    # Test 1: Initialize
    print("1. Testing 'initialize'...")
    req_init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }
    }
    handle_request(req_init)

    # Test 2: Tools List
    print("\n2. Testing 'tools/list'...")
    req_tools = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    handle_request(req_tools)

    # Test 3: List Jobs
    print("\n3. Testing 'tools/call' for 'list_jobs'...")
    req_call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "list_jobs",
            "arguments": {"limit": 3}
        }
    }
    handle_request(req_call)
    print("\n=== Self-Test Completed Successfully ===")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_self_test()
    else:
        run_server()
