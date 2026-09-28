# 프로젝트에서 쓰는 폴더 경로. 실행 위치(cwd)와 상관없이 이 파일 위치를 기준으로 찾는다.
from pathlib import Path

# paths.py → cctv_intrusion → src → 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CCTV_DIR = DATA_DIR / "cctv"  # CCTV 탭에서 재생할 영상
SCREENS_DIR = CCTV_DIR / "screens"  # 화면(슬롯)별 위험구역 JSON
OUTPUT_DIR = DATA_DIR / "output"  # (레거시/기타) 침입 클립은 recordings/ 의 .mp4 사용
RECORDINGS_DIR = DATA_DIR / "recordings"  # cam1~cam4 하위에 상시 .ts · 침입 .mp4 · events.csv
MODELS_DIR = PROJECT_ROOT / "models"  # YOLO 모델 (최초 실행 때 자동 다운로드, 커밋 안 함)

SCREEN_COUNT = 4


def screen_recordings_dir(screen_index: int, *, create: bool = True) -> Path:
    """CAM N 상시 녹화·침입 클립·CSV 폴더 (recordings/camN/)."""
    path = RECORDINGS_DIR / f"cam{screen_index}"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
