# CCTV Intrusion Detection


| 항목              | 내용                                                                                                                                     |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **버전**          | `0.1.0` (`pyproject.toml`)                                                                                                             |
| **패키지명**        | `cctv-intrusion`                                                                                                                       |
| **팀**           | 14팀                                                                                                                                    |
| **팀원**          | 이재선, 김태수                                                                                                                               |
| **형상관리**        | [GitHub —](https://github.com/JaeSeon-Lee/cctv-intrusion-detection/tree/fix/webcam-recording-timeline) `fix/webcam-recording-timeline` |
| **Python**      | **3.12** (`requires-python >= 3.12`)                                                                                                   |
| **OS**          | macOS (Apple Silicon 권장), Windows / Linux                                                                                              |
| **환경**          | conda `cctv-ai` + pip (`requirements.txt` 버전 고정)                                                                                       |
| **LLM / AI 보조** | Cursor — **Composer, Claude**                                                                                                          |


## 개발환경 · 사용 스택


| 구분     | 기술                        | 버전(고정)           | 역할                           |
| ------ | ------------------------- | ---------------- | ---------------------------- |
| UI     | PySide6 (Qt)              | 6.11.2           | 4분할 모니터, 다시보기, 구역 편집         |
| 영상 입출력 | OpenCV                    | 5.0.0            | 웹캠·파일 디코드, 프레임 처리            |
| 배열     | NumPy                     | 2.5.3            | 프레임 버퍼                       |
| 사람 탐지  | Ultralytics **YOLO11s**   | 8.4.163          | `yolo11s.pt` 사람 박스 추론        |
| 추론 엔진  | PyTorch                   | 2.14.0           | CUDA / Apple MPS / CPU 자동 선택 |
| 녹화·클립  | **ffmpeg** (시스템)          | PATH             | 상시 MPEG-TS 기록, 침입 구간 mp4 절단  |
| 품질     | ruff / pytest / pytest-qt | 0.16 / 9.1 / 4.5 | 린트·테스트                       |


---



### 과제 평가


| 항목           | 내용                                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------------- |
| **완성도**      | 상                                                                                                                   |
| **과제 난이도**   | LLM 사용: **하** · 미사용: **상**                                                                                          |
| **참여도**      | 이재선 **40%** · 김태수 **60%**                                                                                           |
| **한계와 개선방향** | 실제 관제는 카메라 4대를 모두 실시간으로 쓰지만, 개발 환경에는 웹캠이 1대뿐이라 CAM2~4는 동영상 파일로 대체했다. 이후 웹캠·IP 카메라를 추가 연결하면 전 화면을 실시간 입력으로 통일할 수 있다. |




## 주제

CCTV 영상 기반 **위험구역 침입 감지** 및 사건 자동 기록

## 개요

공장·시설 CCTV 관제와 비슷하게, 여러 화면을 동시에 보며 사용자가 지정한 폴리곤 위험구역에
사람이 일정 시간 머물면 경보를 울리고, 상시 녹화·침입 클립·사건 CSV를 자동으로 남기는
Computer Vision / 데스크톱 관제 앱이다.

- 4분할 CCTV 모니터 (CAM1 웹캠, CAM2~4 파일 영상)
- 화면별 위험구역 편집 (등급: 감지 / 주의 / 위험)
- YOLO11s로 사람 탐지 → **발 위치** 기준 구역 교차 + 체류 시간으로 경보
- 상시 녹화(`.ts`) + 침입 시 상시 파일에서 구간을 잘라 클립(`live_*.mp4`)·`events.csv` 저장
- 다시보기·대시보드로 사건 확인



## Pipeline (로직 · 사용 기술)

한 줄 흐름:

```
영상 입력 → YOLO 사람 탐지 → 발점×위험구역 → 체류 시간 필터
  → 경보/해제 → 상시 .ts 녹화 → (사건 종료 후) .ts 구간 절단 → CSV/다시보기
```



### 단계별 상세


| 단계              | 무엇을 하나                                                  | 무엇으로 하나                                                                                |
| --------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **1. 영상 입력**    | CAM1 웹캠, CAM2~4는 `camN.mp4` 또는 파일 트리에서 할당. 파일은 반복 재생.   | OpenCV `VideoCapture` / 웹캠 캡처 스레드, PySide6 타이머로 화면 갱신                                  |
| **2. 사람 탐지**    | 프레임에서 사람 박스(x1,y1,x2,y2)를 구함. UI를 막지 않도록 **워커 스레드 1개**. | Ultralytics YOLO11s + PyTorch (MPS/CUDA/CPU). **캠별 최신 1장 큐** — 밀리면 중간 프레임은 버리고 공평하게 순회 |
| **3. 침입 공간 판정** | 박스 전체가 아니라 **발 위치** `((x1+x2)/2, y2)` 가 폴리곤 안인지 검사      | NumPy / 폴리곤 포함 판정 (`IntrusionMonitor`)                                                 |
| **4. 시간 필터**    | 구역 등급별 체류 초(감지 3s / 주의 2s / 위험 1s) 이상이면 경보              | `MonitorState`: idle → armed → alarm → cleared                                         |
| **5. 화면 표시**    | 구역·YOLO 박스·상태 배지·경보 시 얇은 빨간 테두리/덮개                      | PySide6 QPainter 오버레이                                                                  |
| **6. 상시 녹화**    | 오버레이가 입혀진 프레임을 캠별 폴더에 계속 기록                             | ffmpeg raw BGR → **MPEG-TS (**`.ts`**)** (`ContinuousRecorder`)                        |
| **7. 침입 클립**    | 경보−3초 ~ 해제+5초 구간을 mp4로 남김. 해제 후 5초 안 재경보면 같은 클립 연장      | 상시 `.ts` **스냅샷 후 ffmpeg 절단** (`IntrusionClipper` + 백그라운드 스레드). CSV에 사건 1줄 추가           |
| **8. 다시보기**     | `.ts` / `live_*.mp4` 재생, 상시 녹화 선택 시 대시보드(침입 비율·타임라인 등)  | OpenCV 재생 + PySide6. 녹화 중 `.ts`는 스냅샷으로 연다                                              |




### 침입 클립: 초기 → 현재


|       | 초기 (`LiveRecorder`)                   | 현재 (`IntrusionClipper`)             |
| ----- | ------------------------------------- | ----------------------------------- |
| 방식    | 매 프레임 JPEG 버퍼 → 경보 시 VideoWriter로 mp4 | 상시 `.ts`만 쓰다가, 사건 끝나면 ffmpeg로 구간 절단 |
| 문제/이점 | 4캠에서 UI 렉·이중 인코딩                      | 평소 부하↓, 사건당 백그라운드 1회 작업             |


> 침입 감지 때마다 프레임을 “변환 큐”에 넣는 구조가 **아님**.
> YOLO용 **캠별 최신 프레임 큐**와, 클립용 **ClipExportJob 1건(백그라운드)** 은 별개다.



### Project Goal (요약)

- CCTV 영상 입력 · Polygon 위험지역 지정
- 사람 검출 · 발 위치 기준 구역 겹침 · 등급별 체류 후 경보
- 침입 영상·이벤트 로그 자동 저장



## 설치 및 실행방법



### 1) 환경 생성 (최초 1회)

```bash
conda env create -f environment.yml   # Python 3.12 + requirements.txt
conda activate cctv-ai
```

이미 `cctv-ai` 환경이 있으면:

```bash
conda activate cctv-ai
pip install -r requirements.txt
```



### 2) 실행

```bash
python -m cctv_intrusion              # 또는 cctv-intrusion
```

처음 실행 시 YOLO 가중치(`yolo11s.pt`, 약 19MB)를 `models/`로 자동 다운로드한다. (인터넷 필요)

macOS는 터미널/IDE에 **카메라 권한**을 허용해야 웹캠(CAM1)이 동작한다.
WSL2는 기본 설정으로 웹캠을 쓰기 어렵다.

### 3) (선택) GPU

앱 시작 시 장치를 자동 선택한다: **CUDA → Apple MPS → CPU**.

```bash
# macOS / CPU 공통
pip install -r requirements.txt

# Windows / Linux + NVIDIA (CUDA 12.4 휠)
pip install -r requirements-cuda.txt
```

터미널에 `사람 탐지 모델 로딩 완료 (장치: mps)` 또는 `cuda:0`이 보이면 GPU 사용 중이다.

### 4) 개발용 명령

```bash
pytest                                # 테스트
ruff check --fix . && ruff format .  # 린트·포맷
```

앱을 **종료한 뒤 다시 실행**할 때는 `data/recordings/cam1`~`cam4`를 지우는 것을 권장한다.
상시 `.ts`가 계속 쌓이므로 데모·테스트 전에 비우면 용량·다시보기 목록이 깔끔하다.

```bash
rm -rf data/recordings/cam1 data/recordings/cam2 data/recordings/cam3 data/recordings/cam4
```



## CCTV 모니터

상단 탭: **CCTV** / **다시보기**

- **CCTV**: 2×2 화면. 시작 시 CAM 1은 웹캠, CAM 2~4는 `data/cctv/camN.mp4` 가 있으면 자동 재생.
  - 화면을 클릭해 선택한 뒤 좌측 목록에서 파일을 누르면 그 화면에 할당된다.
  - 위험구역은 **화면 단위**로 `data/cctv/screens/screen_N.json` 에 저장된다 (영상을 바꿔도 유지).
  - 목록에서 구역을 고른 뒤 **구역 삭제** 버튼(또는 Delete 키)으로 지울 수 있다.
- 상시 녹화·침입 클립·CSV 는 캠별 폴더 `data/recordings/camN/` 에 저장된다.
  - 상시 녹화: `{YYYYmmdd_HHMMSS}.ts` (화면 오버레이 포함)
  - 침입 클립: `live_YYYYmmdd_HHMMSS.mp4` — 상시 `.ts` 에서 경보 전 3초~해제 후 5초를 잘라 저장
  (웹캠·파일 캠 동일. 해제 후 5초 안 재경보면 **같은 구간을 늘려** 한 파일로 자름)
  - 사건 CSV: `events.csv` (경보가 **해제될 때** 한 줄 추가)
- **다시보기**: 좌측에서 상시 녹화(`.ts`) 또는 침입 클립(`.mp4`)을 골라 재생한다.
  - 상시 녹화(`.ts`)를 선택하면 **[대시보드]** 버튼이 활성화된다 (폴더·침입 클립 선택 시 비활성).
  - 대시보드는 `events.csv` 중 그 녹화(`source_file`)의 행으로 녹화 길이 대비 침입 비율(%, 겹친 구간은 한 번만),
  침입 횟수, 평균·최장 지속 시간, 녹화 타임라인, 침입별 지속 시간 막대 그래프, 사건 표를 보여준다.
  - `source_*` 컬럼이 없는 예전 기록은 어느 녹화인지 알 수 없어 집계에서 빠진다.



#### 침입 사건 CSV (`data/recordings/camN/events.csv`)


| 컬럼                  | 설명                                        |
| ------------------- | ----------------------------------------- |
| `alarm_at`          | 경보 확정 시각 (침입 클립 기준, `MM:SS.mmm`)          |
| `cleared_at`        | 경보 해제 시각                                  |
| `duration_sec`      | 경보~해제 지속 시간(초)                            |
| `clip_start`        | 클립 시작 = `alarm_at` − 3초                   |
| `clip_end`          | 클립 끝 = `cleared_at` + 5초                  |
| `clip_file`         | 같은 폴더의 침입 클립 파일명                          |
| `zone_name`         | 침입한 위험구역 이름                               |
| `zone_level`        | 구역 등급 (`detect` / `caution` / `danger`)   |
| `source_file`       | 클립을 자른 상시 녹화 파일명 (`{YYYYmmdd_HHMMSS}.ts`) |
| `source_alarm_at`   | 상시 녹화 파일 기준 경보 시각 (대시보드용)                 |
| `source_cleared_at` | 상시 녹화 파일 기준 해제 시각                         |




## 프로젝트 구조

```
├── pyproject.toml / requirements.txt / environment.yml
├── data/cctv · data/cctv/screens · data/recordings/camN
├── models/                     # YOLO 가중치 (자동 다운로드)
├── src/cctv_intrusion/
│   ├── app.py / __main__.py    # 진입점
│   ├── paths.py
│   ├── ui/                     # PySide6 (main_window, widget/, styles/)
│   │   └── widget/             # file_tree, camera_grid, video_*, zone_panel
│   ├── video/                  # OpenCV 입출력 · 상시 녹화(ffmpeg)
│   ├── intrusion/              # 침입 판정 · 사건 CSV · 클립 절단
│   ├── zone/                   # Zone 모델 · 등급 · json 저장
│   └── detection/              # YOLO 사람 탐지 (워커 스레드)
└── tests/
```

