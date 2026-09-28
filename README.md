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

### 실시간 영상 / 저장된 동영상

왼쪽 탭에서 입력을 고른다. 위험구역 설정·경보는 두 탭이 같다.

- **실시간 영상**: 카메라 번호(내장 카메라는 보통 0번)를 고르고 [연결]한다.
  위험구역은 `data/input/camera_0.json` 처럼 카메라 번호별로 저장된다 (PC마다 달라 커밋하지 않음).
  침입이 감지되면 경보 3초 전 ~ 해제 5초 후를 `data/output/live_YYYYmmdd_HHMMSS.mp4` 로 녹화하고,
  같은 이름의 `.csv` 에 사건을 기록한다 (CSV 시각은 클립 안의 시각).
- **저장된 동영상**: `data/` 아래 영상 파일을 골라 재생한다. 사건은 `data/output/{영상이름}_N.mp4` / `{영상이름}.csv`.

macOS 는 처음 연결할 때 터미널(또는 IDE)에 카메라 권한을 허용해야 한다. WSL2 는 기본 설정으로는 웹캠을 쓸 수 없다.

### 사람 탐지 GPU 사용 (선택)

`requirements.txt` 는 용량이 작은 **CPU 전용 torch**(약 200MB)를 설치한다.
Apple Silicon(MPS)이나 NVIDIA CUDA가 있으면 코드가 자동으로 그쪽을 쓰고, 추론 해상도(`imgsz=1280`)로 작은 사람 탐지를 보강한다.
CPU만 있으면 프레임당 약 200ms 안팎이라 박스는 재생보다 덜 자주 갱신될 수 있다.
NVIDIA GPU를 쓰고 싶으면 [PyTorch 설치 페이지](https://pytorch.org/get-started/locally/)에서 CUDA 버전 설치 명령을 확인해
같은 버전(`torch==2.14.0`)으로 다시 설치한다.

## 프로젝트 구조

```
├── pyproject.toml / requirements.txt / environment.yml
├── data/input · data/output
├── models/                     # YOLO 가중치 (자동 다운로드)
├── src/cctv_intrusion/
│   ├── app.py / __main__.py    # 진입점
│   ├── paths.py
│   ├── ui/                     # PySide6 (main_window, widget/, styles/)
│   │   └── widget/             # file_tree, camera_panel, video_*, control_bar, zone_panel
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
- Ultralytics 8.4 (YOLO11s) + PyTorch 2.14 (CPU): 사람 탐지
- ruff, pytest, pytest-qt: 개발 도구
