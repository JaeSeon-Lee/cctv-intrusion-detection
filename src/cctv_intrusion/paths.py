# 프로젝트에서 쓰는 폴더 경로. 실행 위치(cwd)와 상관없이 이 파일 위치를 기준으로 찾는다.
from pathlib import Path

# paths.py → cctv_intrusion → src → 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CCTV_DIR = DATA_DIR / "cctv"  # CCTV 탭에서 재생할 영상
SCREENS_DIR = CCTV_DIR / "screens"  # 화면(슬롯)별 위험구역 JSON
INPUT_DIR = DATA_DIR / "input"  # 레거시 (테스트 샘플 등)
OUTPUT_DIR = DATA_DIR / "output"  # 침입 클립·CSV
RECORDINGS_DIR = DATA_DIR / "recordings"  # 상시 녹화본 (다시보기 탭)
MODELS_DIR = PROJECT_ROOT / "models"  # YOLO 모델 (최초 실행 때 자동 다운로드, 커밋 안 함)

SCREEN_COUNT = 4
