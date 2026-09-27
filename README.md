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

### 사람 탐지 GPU 사용 (선택)

`requirements.txt` 는 용량이 작은 **CPU 전용 torch**(약 200MB)를 설치한다. CPU에서도 yolo11s는 프레임당 약 70ms라, 재생은 그대로 하면서 박스는 초당 10번 이상 갱신된다.
NVIDIA GPU를 쓰고 싶으면 [PyTorch 설치 페이지](https://pytorch.org/get-started/locally/)에서 CUDA 버전 설치 명령을 확인해
같은 버전(`torch==2.14.0`)으로 다시 설치한다. (CUDA 라이브러리 포함 수 GB) 코드는 GPU가 있으면 자동으로 GPU를 사용한다.

## 프로젝트 구조

```
├── pyproject.toml          # 패키지 정보, 의존성(최소 버전), ruff/pytest 설정
├── requirements.txt        # 팀 공통 고정 버전
├── environment.yml         # conda 환경 (python 3.12 + requirements.txt)
├── data/
│   ├── input/              # 입력 영상
│   └── output/             # 침입 클립 저장 위치
├── models/                 # YOLO 모델 파일 (자동 다운로드, 커밋 안 함)
├── src/cctv_intrusion/
│   ├── __main__.py         # python -m cctv_intrusion 진입점
│   ├── app.py              # QApplication 실행
│   ├── paths.py            # data/, models/ 경로 상수 (DATA_DIR, OUTPUT_DIR, MODELS_DIR ...)
│   ├── ui/                 # PySide6 화면 (main_window, widget/, styles/)
│   ├── video/              # OpenCV 영상 입출력
│   ├── zone/               # 위험구역 파일 저장·불러오기
│   └── detection/          # YOLO 사람 탐지 (워커 스레드)
└── tests/                  # pytest
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
