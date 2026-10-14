# OnlyYou-Fancam (온리유 직캠) 🌟
> **"당신만을 바라보는 시선, 너만 보고 싶은 팬을 위한 AI 자동 9:16 직캠 생성기"**  
> *AI-Powered Multi-Person Video Tracker & Cinematic 9:16 Fancam Generator*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-DNN-red.svg)](https://opencv.org)

---

## 📖 소개 (Introduction)

**OnlyYou-Fancam**은 무대 영상, 댄스 퍼포먼스, 스포츠 경기 등 다수의 인물이 등장하는 영상에서 각 인물을 자동으로 식별·분류하고, 선택된 인물을 9:16 비율(720x1280)의 세로 직캠 MP4로 자동 제작해 주는 오픈소스 AI 솔루션입니다.

Apple의 미니멀리즘 디자인("Simple is Best")을 채택하여 복잡한 설정 없이 영상 파일 드래그 또는 유튜브 링크 하나만으로 원클릭 완성이 가능합니다.

---

## ✨ 핵심 기능 (Key Features)

1. **완벽한 중앙 구도 유지 (Strict 9:16 Centering & Black Padding)**
   - 퍼포머가 무대 외곽($X < 0$ 또는 $X > 1$)으로 이동하더라도 9:16 비율과 인물 중심 구도를 칼같이 유지합니다.
   - 프레임 경계를 벗어나는 영역은 프레임 왜곡 없이 순수 블랙(`RGB [0,0,0]`)으로 자연스럽게 패딩 처리됩니다.

2. **와이드 강제 전환 방지 (Zero Wide-Fallback & Cinematic Glide)**
   - 인물이 무대 밖으로 퇴장하거나 잠시 가려지더라도 억지스러운 전체 샷(와이드 앵글)으로 빠지지 않습니다.
   - 마지막 추적 위치를 부드럽게 홀드(Hold)한 뒤, 인물이 재등장할 때 $C^1$ 연속 Hermite Smoothstep 곡선으로 시네마틱하게 재포착(Glide)합니다.

3. **초저저크 짐벌급 안정화 (Sub-Pixel Anti-Jitter)**
   - 양방향 영위상(Zero-Phase) 가우시안 필터와 속도 적응형 스무딩을 결합하여, 댄스 관절 동작 시 발생하는 미세 떨림과 카메라 헌팅을 원천 제거했습니다. (평균 저크 0.01 norm/s³ 이하 달성)

4. **웹 스트리밍 Faststart & 무손실 오디오 동기화**
   - H.264 Faststart (`moov` atom 선두 배치)가 적용되어 브라우저에서 다운로드 완료를 기다리지 않고 즉시 스트리밍 재생할 수 있습니다.
   - 원본 오디오(AAC 192k)를 샘플 단위로 동기화하여 A/V 싱크 오차 15ms 이하를 보장합니다.

5. **유니버설 옴니바 & 유튜브 다운로드 지원**
   - 로컬 파일 드래그 앤 드롭, 로컬 파일 경로 입력, 유튜브 링크(`youtube.com`, `youtu.be`, `shorts`)를 단일 옴니바에서 자동 처리합니다.

---

## 🚀 빠른 시작 (Quick Start)

### 1. 사전 요구사항
- Python 3.10 이상
- FFmpeg (시스템에 설치되어 있거나 `imageio-ffmpeg`를 통해 자동 로드)

### 2. 설치
```bash
git clone https://github.com/Aminoragit/OnlyYou-Fancam.git
cd OnlyYou-Fancam
pip install -r requirements.txt
```

### 3. 웹 스튜디오 실행 (Apple Inspired Web UI)
```bash
python main.py
```
브라우저에서 `http://127.0.0.1:8000`에 접속하여 직관적인 웹 스튜디오를 사용하실 수 있습니다.

### 4. CLI 직접 실행
```bash
# 로컬 비디오 파일 직접 변환
python main.py --video "storage/test_data/nmixx_dice_test.mp4"

# 유튜브 링크 직접 변환
python main.py --youtube "https://www.youtube.com/watch?v=..."
```

---

## 📁 프로젝트 구조 (Architecture)

```
OnlyYou-Fancam/
├── core/
│   ├── camera_planner.py   # 시네마틱 카메라 패스 생성 (영위상 필터, 활주 보간)
│   ├── config.py           # 시스템 해상도 및 검출 설정
│   ├── detector.py         # 레터박스 전처리 YOLOv8n ONNX 추론기 (자동 다운로드)
│   ├── downloader.py       # yt-dlp 기반 유튜브 다운로더
│   ├── global_resolver.py  # 비중첩 제약 기반 인물 글로벌 클러스터링
│   ├── pipeline.py         # Fast Lane 스캔 & Export Lane 렌더링 파이프라인
│   ├── reid.py             # 3단 공간 피라미드 외형 특징 추출기
│   ├── renderer.py         # 9:16 블랙 패딩 및 Faststart MP4 인코더
│   └── tracker.py          # 샷 체인지 분할 & 다중 객체 트래커
├── web/
│   ├── server.py           # FastAPI 비동기 스트리밍 백엔드 (No-Cache 미들웨어)
│   └── static/             # Apple 스타일 미니멀 웹 스튜디오 (HTML/CSS/JS)
├── models/                 # AI 모델 가중치 폴더 (.gitignore 제외)
├── storage/                # 작업 산출물 및 테스트 데이터
├── requirements.txt        # 종속성 목록
├── LICENSE                 # Apache 2.0 라이선스
└── main.py                 # 진입점 CLI & 웹 서버 런처
```

---

## 📜 라이선스 (License)

본 프로젝트는 **[Apache License 2.0](LICENSE)**에 따라 배포됩니다.
- 상업적 이용, 수정, 배포, 특허권 이용이 자유롭게 허용됩니다.
- 단, 런타임에 자동 다운로드되는 YOLOv8n 모델 가중치는 Ultralytics의 AGPL-3.0 정책이 적용되므로, 순수 상업용 배포 시 YOLOX 또는 YOLOv6(Apache 2.0) 가중치로 손쉽게 교체할 수 있도록 설계되어 있습니다.
