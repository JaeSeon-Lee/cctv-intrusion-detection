from functools import cache
from pathlib import Path

# .qss 파일이 있는 폴더. 실행 위치(cwd)와 상관없이 이 파일 기준으로 찾는다.
STYLE_DIR = Path(__file__).parent


@cache
def load_qss(name: str) -> str:
    """styles/<name>.qss 내용을 읽어서 돌려준다. (같은 파일은 한 번만 읽고 재사용)"""
    return (STYLE_DIR / f"{name}.qss").read_text(encoding="utf-8")
