# 프로젝트에서 쓰는 폴더 경로. 실행 위치(cwd)와 상관없이 이 파일 위치를 기준으로 찾는다.
from pathlib import Path

# paths.py → cctv_intrusion → src → 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"  # 침입 클립 저장 위치 (팀원 모듈도 이 상수를 import 해서 사용)
MODELS_DIR = PROJECT_ROOT / "models"  # YOLO 모델 파일 (최초 실행 때 자동으로 내려받음, 커밋 안 함)
