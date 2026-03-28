"""
공통 유틸리티
"""

from pathlib import Path

# Z: 드라이브 내 폴더 생성 경로
TARGET_BASE = Path(r"Z:\2 제품개발팀\【1】 3D 의뢰파일")

# 확장자별 아이콘
EXT_ICONS = {
    ".stl": "🧊",
    ".obj": "🧊",
    ".3mf": "🧊",
    ".pdf": "📕",
    ".xlsx": "📗",
    ".xls": "📗",
    ".dwg": "📐",
    ".dxf": "📐",
    ".zip": "🗜️",
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
    ".png": "🖼️",
}


def check_drive() -> bool:
    """Z: 드라이브 및 대상 경로 접근 가능 여부 확인"""
    return TARGET_BASE.exists()


def make_folder(product: str, company: str, date: str) -> Path:
    """
    날짜_아이템명_업체명 형식으로 폴더 생성
    예) 260326_부품 2종_올로스코프
    """
    folder_name = f"{date}_{product}_{company}"
    dest = TARGET_BASE / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    return dest
