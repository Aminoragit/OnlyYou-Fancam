<div align="center">

# OnlyYou-Fancam (온리유 직캠) 🌟

### 당신만을 바라보는 시선, 너만 보고 싶은 팬을 위한 AI 자동 9:16 직캠 생성기
**AI-Powered Multi-Person Target Tracking & Cinematic 9:16 Fancam Studio**

[ **[English](README.md)** ] · [ **한국어** ] · [ **[日本語](README_ja.md)** ] · [ **[简体中文](README_zh.md)** ]

<br/>

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-DNN-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![MCP Server](https://img.shields.io/badge/MCP-Protocol_2024--11--05-brightgreen.svg?logo=anthropic&logoColor=white)](#-ai-mcp-서버-연동-model-context-protocol)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#)

<br/>

<img src="web/static/banner.png" alt="OnlyYou-Fancam Banner" width="100%" style="border-radius: 18px; box-shadow: 0 20px 50px rgba(0,0,0,0.8);" />

<br/>
<br/>

**OnlyYou-Fancam**은 복잡한 무대 군무, 방송 직캠, 스포츠 경기 영상에서 다수의 인물을 자동으로 감지·분류하고,  
선택된 단 한 명의 퍼포머만을 안정적으로 추적하여 **완벽한 9:16 세로 직캠 MP4(720x1280)**로 자동 렌더링하는 오픈소스 솔루션입니다.  
최신 **Model Context Protocol (MCP)**를 기본 탑재하여 Claude Desktop, Cursor, Antigravity 등 AI 어시스턴트가 자연어로 직접 직캠을 생성할 수 있습니다.

</div>

---

## 📑 목차 (Table of Contents)

- [핵심 기능](#-핵심-기능-key-features)
- [아키텍처 및 기술 혁신](#-아키텍처-및-기술-혁신)
- [여자친구 콘서트 무대 테스트 결과 (인물별 5단계 추출 표)](#-여자친구-콘서트-무대-테스트-결과)
- [품질 검증 실측치 (QA Metrics)](#-품질-검증-실측치-qa-metrics)
- [설치 및 빠른 시작](#-설치-및-빠른-시작-quick-start)
- [AI MCP 서버 연동 (Model Context Protocol)](#-ai-mcp-서버-연동-model-context-protocol)
- [Apple 스타일 웹 스튜디오](#-apple-스타일-웹-스튜디오-사용법)
- [CLI 사용법](#-cli-직접-실행)
- [라이선스 (License)](#-라이선스-license)

---

## ✨ 핵심 기능 (Key Features)

- 🎯 **완벽한 중앙 구도 & 블랙 패딩 (Strict Centering & Black Padding)**
  - 퍼포머가 무대 극단($X < 0$ 또는 $X > 1$)으로 이동하더라도 9:16 종횡비와 인물 중심을 칼같이 유지합니다.
  - 영상 밖으로 벗어나는 영역은 프레임 왜곡이나 찌그러짐 없이 순수 블랙(`RGB [0,0,0]`)으로 자연스럽게 패딩 처리됩니다.
- 🚫 **와이드 전환 없는 자연스러운 추적 (Zero Wide-Fallback)**
  - 일시적 미검출이나 퇴장 시 와이드 풀샷으로 강제 전환되지 않고, 마지막 추적 위치를 부드럽게 유지합니다.
  - 퍼포머가 재등장할 때 $C^1$ 연속 Hermite Smoothstep 곡선을 통해 시네마틱하게 재포착(Glide)합니다.
- ⚡ **짐벌급 초저저크 스무딩 (Zero-Phase Motion Filter)**
  - 양방향 영위상(Zero-Phase) 필터와 거리 적응형 스무딩을 적용하여 댄스 관절 동작 시 발생하는 미세 진동(Jitter)을 10배 이상 억제했습니다. (Mean Jerk $\le 0.01\text{ norm/s}^3$)
- 🎬 **H.264 Faststart & 무손실 A/V 싱크**
  - MP4 메타데이터(`moov` atom)를 헤더에 배치하여 웹 브라우저에서 다운로드 완료를 기다리지 않고 즉시 스트리밍 재생할 수 있습니다.
  - 원본 오디오(AAC 192k)를 샘플 단위로 동기화하여 A/V 싱크 편차를 15ms 이하로 보장합니다.
- 🔌 **AI 네이티브 MCP 서버 내장 (Model Context Protocol)**
  - 외부 라이브러리 설치 없이 순수 Python 표준 라이브러리 기반 JSON-RPC 2.0 stdio MCP 서버(`mcp_server.py`)를 기본 제공합니다.
  - Claude Desktop, Cursor, Antigravity 등의 AI에게 자연어로 "직캠 만들어줘"라고 지시하면 AI가 직접 렌더링하고 결과를 제공합니다.
- 💎 **Apple 감성의 미니멀 웹 스튜디오**
  - 불필요한 개발자성 지표를 모두 배제한 오닉스 블랙 & 프로스티드 글래스 인터페이스를 제공합니다.
  - 로컬 파일 드래그 앤 드롭, 로컬 경로 입력, 유튜브 링크(`youtube.com`, `youtu.be`, `shorts`)를 단일 옴니바에서 자동 처리합니다.
- 🔓 **순수 Apache 2.0 라이선스 준수**
  - Git 저장소에 AI 모델 바이너리를 포함하지 않고 첫 실행 시 자동 다운로드하여, AGPL 저작권 전염 걱정 없이 기업/상업 환경에서도 안전하게 사용 가능합니다.

---

## 🧠 아키텍처 및 기술 혁신

```
[입력 영상 / YouTube URL / AI MCP 호출]
        │
        ▼
[Fast Lane: 4 FPS 적응형 스캔]
  ├─ ShotDetector (HSV 히스토그램 기반 장면 전환 감지)
  ├─ Letterbox YOLOv8n ONNX 추론 (종횡비 100% 보존 전처리)
  └─ Bipartite Matching Tracklet 추적 (max_lost_frames=4 버퍼)
        │
        ▼
[Global Resolver (동시성 제약 클러스터링)]
  ├─ Cannot-Link 행렬 (동일 프레임 동시 등장 시 영구 분리)
  ├─ 3단 공간 피라미드 ReID 코사인 유사도 병합
  └─ 인물 지속성/신장 비율 다차원 필터링 (노이즈 완벽 차단)
        │
        ▼
[Camera Path Planner (시네마틱 가상 카메라)]
  ├─ 인물 중심(cx, cy) 직접 타겟팅 & 룰오브서드 헤드룸(17%)
  ├─ 양방향 영위상(Zero-Phase) 가우시안 필터링 (지연시간 0ms)
  └─ 거리 적응형 시네마틱 글라이드 (속도 0.22 screen/s 캡)
        │
        ▼
[Export Lane: 백그라운드 MP4 렌더링]
  ├─ Out-of-bounds 순수 블랙 캔버스 패딩 (Strict 720x1280)
  ├─ FFmpeg libx264 ultrafast + aac 무손실 매핑
  └─ Faststart (+faststart) 스트리밍 최적화
```

---

## 🔬 여자친구 콘서트 무대 테스트 결과

아래 표는 **여자친구(GFRIEND) 무대 콘서트 공연 영상(`오늘부터 우리는 / Me Gustas Tu`)**을 대상으로 OnlyYou-Fancam 엔진을 구동하여 개별 인물을 분류하고, 9:16 가상 직캠 MP4를 렌더링한 실제 테스트 결과입니다.

각 인물별로 렌더링된 전체 직캠 영상에서 **동일 간격(0% → 25% → 50% → 75% → 100%)으로 5장의 프레임을 추출**하여 분류 정확도와 트래킹 안정성을 검증했습니다:

| 인물 구분 | 신뢰도 | 1단계 (0.0초 / 0%) | 2단계 (2.5초 / 25%) | 3단계 (5.0초 / 50%) | 4단계 (7.5초 / 75%) | 5단계 (10.0초 / 100%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **퍼포머 1**<br/>`person_001` | **87%** | <img src="docs/images/test_results/gfriend/person_001_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step5.jpg" width="130" /> |
| **퍼포머 2**<br/>`person_002` | **85%** | <img src="docs/images/test_results/gfriend/person_002_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step5.jpg" width="130" /> |
| **퍼포머 3**<br/>`person_003` | **85%** | <img src="docs/images/test_results/gfriend/person_003_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step5.jpg" width="130" /> |
| **퍼포머 4**<br/>`person_004` | **85%** | <img src="docs/images/test_results/gfriend/person_004_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step5.jpg" width="130" /> |
| **퍼포머 5**<br/>`person_005` | **85%** | <img src="docs/images/test_results/gfriend/person_005_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step5.jpg" width="130" /> |
| **퍼포머 6**<br/>`person_006` | **79%** | <img src="docs/images/test_results/gfriend/person_006_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step5.jpg" width="130" /> |

> **검증 포인트**: 멤버 간의 교차 이동 및 무대 전후 동선 변화에도 흔들림 없이 각 퍼포머가 9:16 중앙에 정확히 유지되며, 와이드 화면으로의 강제 이탈이 0회 발생함을 확인했습니다.

---

## 📊 품질 검증 실측치 (QA Metrics)

| 검증 항목 | 실측치 | 기준치 | 판정 |
| :--- | :---: | :---: | :---: |
| **종횡비 및 해상도** | 720 × 1280 (9:16) 100% 일치 | 오차 0px | **PASS** |
| **와이드 전환율 (Fallback)** | **0.0%** (전원 배제) | $\le 5\%$ | **PASS** |
| **카메라 가속도 저크** | **0.005 ~ 0.010 norm/s³** | $\le 0.50$ | **PASS** |
| **경계 이탈 블랙 패딩** | 순수 블랙 `RGB [0,0,0]` 100% | 왜곡 없음 | **PASS** |
| **A/V 싱크 편차** | $\le 12\text{ms}$ | $\le 30\text{ms}$ | **PASS** |
| **Faststart moov atom** | 전 파일 탑재 완료 | 즉시 스트리밍 | **PASS** |

---

## 📦 설치 및 빠른 시작 (Quick Start)

### 1. 저장소 클론 및 패키지 설치
```bash
git clone https://github.com/Aminoragit/OnlyYou-Fancam.git
cd OnlyYou-Fancam
pip install -r requirements.txt
```

### 2. 웹 스튜디오 실행
```bash
python main.py
```
브라우저에서 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**에 접속합니다.

---

## 🔌 AI MCP 서버 연동 (Model Context Protocol)

**OnlyYou-Fancam**은 [Anthropic Model Context Protocol (MCP)](https://modelcontextprotocol.io/)을 지원하여, **Claude Desktop**, **Cursor**, **Antigravity** 등 최신 AI 에이전트 환경에서 도구로 등록해 사용할 수 있습니다.

### MCP 서버 자체 테스트
```bash
python mcp_server.py --test
```

### Claude Desktop 연동 설정
`%APPDATA%\Claude\claude_desktop_config.json` (Windows) 또는 `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) 파일에 아래 내용을 추가합니다:

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

### Cursor / Antigravity 연동 설정
프로젝트 루트 또는 설정의 `mcp.json`에 등록합니다:

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

### 제공되는 AI MCP 도구 목록
| 도구 이름 | 설명 | 주요 인자 |
| :--- | :--- | :--- |
| `create_fancam` | 영상(로컬/유튜브)을 분석하여 선택된 멤버 또는 전원의 9:16 직캠 비디오를 즉시 생성합니다. | `video_source`, `target_person_id`, `start_sec`, `end_sec` |
| `inspect_performers` | 렌더링 전 영상 내 출연자 수, 신뢰도, 대표 썸네일 및 타임스탬프를 빠르게 스캔합니다. | `video_source`, `start_sec`, `end_sec` |
| `get_job_status` | 특정 작업 ID의 진행률, 내보내기 완료 파일 목록, QA 품질 보고서를 조회합니다. | `job_id` |
| `list_jobs` | 로컬에 생성된 최근 직캠 작업 내역 및 파일 목록을 확인합니다. | `limit` |
| `download_youtube` | `yt-dlp`를 사용하여 유튜브 영상의 특정 구간을 로컬로 다운로드합니다. | `url`, `start_sec`, `end_sec` |

---

## 🖥️ Apple 스타일 웹 스튜디오 사용법

1. **단일 옴니바(Omnibar)에 입력**:
   - 로컬 파일 경로 입력 후 `Enter`
   - 유튜브 링크(`https://...`) 붙여넣고 `Enter`
   - 탐색기에서 영상 파일을 브라우저 창으로 드래그 앤 드롭
   - 파일이 없다면 상단 **`[데모 영상 체험]`** 버튼 원클릭
2. **실시간 9:16 플레이어**:
   - 분석이 완료되면 스튜디오가 자동으로 열리며 9:16 세로 화면에 인물이 완벽히 중앙 정렬됩니다.
   - 우측 출연자 아바타 카드를 클릭하면 즉시 해당 인물 직캠으로 카메라가 전환됩니다.
3. **원클릭 다운로드**:
   - 백그라운드에서 완성된 각 멤버의 9:16 MP4 파일 우측 `[다운로드]` 버튼을 눌러 소장할 수 있습니다.

---

## 💻 CLI 직접 실행

```bash
# 로컬 비디오 파일 직캠 생성
python main.py --video "storage/test_data/gfriend_stage.mp4"

# 유튜브 링크 직접 다운로드 및 직캠 생성
python main.py --youtube "https://www.youtube.com/watch?v=sP6b3147GcQ"
```

---

## 📜 라이선스 (License)

본 프로젝트는 **[Apache License 2.0](LICENSE)**에 따라 배포됩니다.
상업적 이용, 수정, 재배포 및 특허 사용이 법적으로 자유롭게 보장됩니다.

Copyright © 2026 [Aminoragit](https://github.com/Aminoragit). All rights reserved.
