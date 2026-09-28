# CCTV Intrusion Detection

CCTV 영상에서 사용자가 지정한 위험지역을 침입하는 움직이는 객체를 탐지하고
침입 사건을 자동으로 기록하는 Computer Vision 프로젝트.

## Project Goal

- CCTV 영상 입력
- 사용자가 Polygon 형태의 위험지역 지정
- 움직이는 객체 검출
- 객체와 위험지역의 공간적 겹침 판단
- N프레임 이상 지속 시 침입 확정
- 침입 영상 자동 저장
- 침입 이벤트 로그 저장

## 실행

```bash
conda env create -f environment.yml   # 최초 1회: python 3.12 + requirements.txt 설치
conda activate cctv-ai
python -m cctv_intrusion              # 또는 cctv-intrusion
```

이미 `cctv-ai` 환경이 있으면 `pip install -r requirements.txt` 만 실행한다.
(팀원 모두 같은 버전을 쓰도록 `requirements.txt` 에 버전이 고정되어 있고, 이 패키지도 editable 모드로 함께 설치된다.)

처음 실행할 때 YOLO 모델(`yolo11s.pt`, 약 19MB)을 `models/` 폴더로 자동으로 내려받는다. (인터넷 연결 필요)

- 테스트: `pytest`
- 린트·포맷: `ruff check --fix . && ruff format .`

### CCTV 모니터

상단 탭: **CCTV** / **기록**(준비 중)

- **CCTV**: 2×2 화면. CAM 1은 웹캠 자동 연결, CAM 2~4는 좌측 `data/cctv` 목록에서 영상을 골라 재생한다.
  - 화면을 클릭해 선택한 뒤 파일을 누르면 그 화면에 할당된다.
  - 위험구역은 **화면 단위**로 `data/cctv/screens/screen_N.json` 에 저장된다 (영상을 바꿔도 유지).
- 침입 사건: 파일 화면은 `data/output/{영상이름}.csv` / `{영상이름}_N.mp4`, 웹캠은 `live_YYYYmmdd_HHMMSS.*`.

macOS 는 처음 연결할 때 터미널(또는 IDE)에 카메라 권한을 허용해야 한다. WSL2 는 기본 설정으로는 웹캠을 쓸 수 없다.

### 사람 탐지 GPU (Mac / Windows)

앱 시작 시 장치를 자동 선택한다: **CUDA → Apple MPS → CPU**.

```bash
# 공통 (macOS 포함 — Apple Silicon 이면 MPS 자동)
pip install -r requirements.txt

# Windows / Linux + NVIDIA GPU (CUDA 12.4 휠로 torch 교체)
pip install -r requirements-cuda.txt
```

터미널에 `사람 탐지 모델 로딩 완료 (장치: mps)` 또는 `cuda:0` 이 보이면 GPU 사용 중이다.
CUDA 버전이 다르면 [PyTorch 설치 페이지](https://pytorch.org/get-started/locally/)에서 `torch==2.14.0`에 맞는 명령을 고른다.

## 프로젝트 구조

```
├── pyproject.toml / requirements.txt / environment.yml
├── data/cctv · data/cctv/screens · data/output
├── models/                     # YOLO 가중치 (자동 다운로드)
├── src/cctv_intrusion/
│   ├── app.py / __main__.py    # 진입점
│   ├── paths.py
│   ├── ui/                     # PySide6 (main_window, widget/, styles/)
│   │   └── widget/             # file_tree, camera_grid, video_*, zone_panel
│   ├── video/                  # OpenCV 입출력 (동영상 파일, 웹캠)
│   ├── intrusion/              # 침입 판정 · 사건 CSV · 클립 저장 (실시간 녹화 포함)
│   ├── zone/                   # Zone 모델 · 등급 · json 저장
│   └── detection/              # YOLO 사람 탐지 (워커 스레드)
└── tests/
```

## Pipeline

CCTV Video
→ Person Detection (YOLO11s)
→ Danger Zone Intersection
→ Temporal Filtering
→ Intrusion Event
→ Recording / Logging

## Tech Stack

- Python 3.12
- PySide6 6.11: UI
- OpenCV 5.0: 영상 입출력
- NumPy 2.5: 프레임 배열
- Ultralytics 8.4 (YOLO11s) + PyTorch 2.14 (CUDA / MPS / CPU): 사람 탐지
- ruff, pytest, pytest-qt: 개발 도구
