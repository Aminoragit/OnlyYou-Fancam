<div align="center">

# OnlyYou-Fancam 🌟

### AI-Powered Multi-Person Target Tracking & Cinematic 9:16 Vertical Fancam Studio

[ **English** ] · [ **[한국어 (Korean)](README_kr.md)** ] · [ **[日本語 (Japanese)](README_ja.md)** ] · [ **[简体中文 (Chinese)](README_zh.md)** ]

<br/>

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-DNN-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![MCP Server](https://img.shields.io/badge/MCP-Protocol_2024--11--05-brightgreen.svg?logo=anthropic&logoColor=white)](#-ai-mcp-server-model-context-protocol)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#)

<br/>

<img src="web/static/banner.png" alt="OnlyYou-Fancam Banner" width="100%" style="border-radius: 18px; box-shadow: 0 20px 50px rgba(0,0,0,0.8);" />

<br/>
<br/>

**OnlyYou-Fancam** is an open-source AI studio designed for devoted fans and content creators.  
It automatically detects, tracks, and isolates individual performers in complex multi-person stage choreographies,  
rendering broadcast-grade **9:16 vertical fancams (720x1280 MP4)** with zero wide-angle dropout,  
sub-sample A/V synchronization, and pure black letterboxing.

Equipped with a built-in **Model Context Protocol (MCP)** server, AI assistants like **Claude Desktop**, **Cursor**, and **Antigravity** can invoke OnlyYou-Fancam directly via natural language tool calls.

</div>

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Test Results & Performer Classification Table](#-test-results--performer-classification)
- [Quality Assurance & Benchmark Metrics](#-quality-assurance--benchmark-metrics)
- [Quick Start & Installation](#-quick-start--installation)
- [AI MCP Server (Model Context Protocol)](#-ai-mcp-server-model-context-protocol)
- [Apple-Inspired Web Studio](#-apple-inspired-web-studio)
- [CLI Usage](#-cli-usage)
- [License](#-license)

---

## ✨ Key Features

- 🎯 **Strict 9:16 Centering & Boundary Black Padding**
  - Keeps the tracked performer dead-center regardless of lateral movement across stage boundaries ($X < 0$ or $X > 1$).
  - Out-of-bounds regions are cleanly padded with pure obsidian black (`RGB [0,0,0]`) without any aspect ratio distortion.
- 🚫 **Zero Wide-Angle Fallback & Cinematic Glide**
  - Temporary occlusions or stage exits do not drop back to wide shot. The camera gracefully maintains the last tracked position and smoothly re-acquires the performer upon reappearance using $C^1$-continuous Hermite smoothstep curves.
- ⚡ **Gimbal-Grade Zero-Phase Motion Filtering**
  - Bidirectional zero-phase Gaussian filtering combined with velocity-adaptive smoothing suppresses arm-flutter jitter by over 10× (Mean Jerk $\le 0.01\text{ norm/s}^3$).
- 🎬 **H.264 Faststart & Lossless A/V Sync**
  - MP4 `moov` atom is positioned at the file header for instantaneous web streaming playback.
  - Source audio (AAC 192kbps) is synchronized at sample resolution with deviation $\le 12\text{ms}$.
- 🔌 **Native AI MCP Server (JSON-RPC 2.0 stdio)**
  - Zero-dependency Model Context Protocol server (`mcp_server.py`) enables Claude Desktop, Cursor, and other AI agents to generate fancams via natural language prompts.
- 💎 **Apple-Inspired Minimalist Web Studio**
  - Onyx Black and frosted glass interface eliminates developer clutter. Drag-and-drop local files, enter local paths, or paste YouTube links (`youtube.com`, `youtu.be`, `shorts`) in a unified omnibar.
- 🔓 **Pure Apache 2.0 Compliance**
  - AI model weights are downloaded on demand on first run, eliminating copyleft viral license risks in commercial and enterprise environments.

---

## 🧠 System Architecture

```
[ Input Video / YouTube URL / AI MCP Tool Call ]
                     │
                     ▼
[ Fast Lane: 4 FPS Adaptive Scanning ]
  ├─ ShotDetector: HSV histogram scene change detection
  ├─ Letterbox YOLOv8n ONNX: Aspect-ratio preserving inference
  └─ Bipartite Matching Tracklet: max_lost_frames=4 buffer
                     │
                     ▼
[ Global Resolver: Cannot-Link Constrained Clustering ]
  ├─ Cannot-Link Matrix: Permanent separation of concurrent performers
  ├─ 3-Level Spatial Pyramid ReID: Cosine similarity matching
  └─ Multi-metric persistence & height ratio filtering
                     │
                     ▼
[ Camera Path Planner: Cinematic Virtual Operator ]
  ├─ Performer centroid (cx, cy) target + Rule-of-Thirds headroom (17%)
  ├─ Zero-Phase Gaussian bidirectional smoothing (0ms latency)
  └─ Velocity-adaptive cinematic glide (max 0.22 screen/s)
                     │
                     ▼
[ Export Lane: Background MP4 Encoding ]
  ├─ Out-of-bounds pure black canvas padding (Strict 720x1280)
  ├─ FFmpeg libx264 ultrafast + lossless AAC audio muxing
  └─ Faststart (+faststart) instant streaming optimization
```

---

## 🔬 Test Results & Performer Classification

The following table presents actual test results obtained from the **GFRIEND Concert Stage Performance** (`Me Gustas Tu`).  
OnlyYou-Fancam's Fast Lane clustering successfully resolved the performers on stage, planned smooth 9:16 virtual camera paths, and rendered individual MP4 fancams.

Below are **5 evenly-spaced frame captures ($0\% \rightarrow 25\% \rightarrow 50\% \rightarrow 75\% \rightarrow 100\%$)** extracted across each performer's entire fancam video:

| Performer ID | Confidence | Frame 1 (0.0s / 0%) | Frame 2 (2.5s / 25%) | Frame 3 (5.0s / 50%) | Frame 4 (7.5s / 75%) | Frame 5 (10.0s / 100%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Performer 01**<br/>`person_001` | **87%** | <img src="docs/images/test_results/gfriend/person_001_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step5.jpg" width="130" /> |
| **Performer 02**<br/>`person_002` | **85%** | <img src="docs/images/test_results/gfriend/person_002_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step5.jpg" width="130" /> |
| **Performer 03**<br/>`person_003` | **85%** | <img src="docs/images/test_results/gfriend/person_003_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step5.jpg" width="130" /> |
| **Performer 04**<br/>`person_004` | **85%** | <img src="docs/images/test_results/gfriend/person_004_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step5.jpg" width="130" /> |
| **Performer 05**<br/>`person_005` | **85%** | <img src="docs/images/test_results/gfriend/person_005_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step5.jpg" width="130" /> |
| **Performer 06**<br/>`person_006` | **79%** | <img src="docs/images/test_results/gfriend/person_006_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step5.jpg" width="130" /> |

> **Key Observation**: Even with complex formation changes, occlusions, and camera motion, each individual performer remains tightly centered with zero wide-angle dropout.

---

## 📊 Quality Assurance & Benchmark Metrics

| Metric | Measured Value | Target Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Resolution & Aspect Ratio** | 720 × 1280 (9:16) Exact | 0 px error | **PASS** |
| **Wide-Angle Fallback Rate** | **0.0%** (Completely Eliminated) | $\le 5\%$ | **PASS** |
| **Camera Acceleration Jerk** | **0.005 ~ 0.010 norm/s³** | $\le 0.50\text{ norm/s}^3$ | **PASS** |
| **Out-of-Bounds Padding** | Pure Black `RGB [0,0,0]` | No distortion | **PASS** |
| **A/V Sync Deviation** | $\le 12\text{ ms}$ | $\le 30\text{ ms}$ | **PASS** |
| **Faststart moov atom** | Verified on all MP4 files | Instant Web Playback | **PASS** |

---

## 📦 Quick Start & Installation

### 1. Clone Repository & Install Dependencies
```bash
git clone https://github.com/Aminoragit/OnlyYou-Fancam.git
cd OnlyYou-Fancam
pip install -r requirements.txt
```

### 2. Launch Web Studio
```bash
python main.py
```
Open your browser and navigate to **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

---

## 🔌 AI MCP Server (Model Context Protocol)

**OnlyYou-Fancam** provides native support for the [Anthropic Model Context Protocol (MCP)](https://modelcontextprotocol.io/), allowing AI assistants such as **Claude Desktop**, **Cursor**, and **Antigravity** to analyze videos and render 9:16 fancams through natural language instructions.

### Run Self-Test
```bash
python mcp_server.py --test
```

### Claude Desktop Configuration
Add the server entry to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "onlyyou-fancam": {
      "command": "python",
      "args": [
        "d:/video_target_tracker/mcp_server.py"
      ]
    }
  }
}
```

### Cursor / Antigravity Configuration
Add to your project's `mcp.json`:

```json
{
  "mcpServers": {
    "onlyyou-fancam": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

### Available MCP Tools

| Tool | Description | Arguments |
| :--- | :--- | :--- |
| `create_fancam` | Analyzes video and renders 9:16 vertical MP4 fancams for specified performer or all performers. | `video_source`, `target_person_id`, `start_sec`, `end_sec` |
| `inspect_performers` | Quickly scans video, estimates performer count K, and returns thumbnail posters and timestamps. | `video_source`, `start_sec`, `end_sec` |
| `get_job_status` | Returns real-time processing progress, exported file paths, and QA report for a job ID. | `job_id` |
| `list_jobs` | Lists recently processed fancam jobs and generated MP4 files. | `limit` |
| `download_youtube` | Downloads video snippet from YouTube via `yt-dlp`. | `url`, `start_sec`, `end_sec` |

---

## 🖥️ Apple-Inspired Web Studio

1. **Unified Omnibar**:
   - Paste a local video path and press `Enter`.
   - Paste a YouTube URL (`https://...`) and press `Enter`.
   - Drag and drop video files directly into the browser window.
   - Click the **`[Demo Video]`** button to test instantly.
2. **Real-time 9:16 Player**:
   - Upon completion, the studio automatically switches to the 9:16 vertical player.
   - Click any performer's avatar in the right panel to instantly focus the virtual camera on that dancer.
3. **One-Click Export**:
   - Download finished 9:16 MP4 files directly from the browser.

---

## 💻 CLI Usage

```bash
# Process a local video file
python main.py --video "storage/test_data/gfriend_stage.mp4"

# Download and process a YouTube video
python main.py --youtube "https://www.youtube.com/watch?v=sP6b3147GcQ"
```

---

## 📜 License

This project is licensed under the **[Apache License 2.0](LICENSE)**.  
Commercial use, modification, redistribution, and sublicensing are freely permitted.

Copyright © 2026 [Aminoragit](https://github.com/Aminoragit). All rights reserved.
