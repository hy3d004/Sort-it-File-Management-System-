"""
공통 유틸리티
"""

from pathlib import Path

# Z: 드라이브 내 폴더 생성 경로
TARGET_3D = Path(r"Z:\2 제품개발팀\【1】 3D 의뢰파일")
TARGET_IMAGE_BASE = Path(r"Z:\1 공통 운영\【09】 아카이브 (촬영물 · 백업)\01 사진·영상 자료\01. 의뢰·제작 제품")

# 하위 호환
TARGET_BASE = TARGET_3D

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


def check_drive(base: Path = TARGET_3D) -> bool:
    """드라이브 및 대상 경로 접근 가능 여부 확인"""
    return base.exists()


def get_image_target() -> Path:
    """현재 연도 기준 이미지 저장 경로 반환"""
    from datetime import datetime
    year = datetime.today().strftime("%Y")
    return TARGET_IMAGE_BASE / f"{year}년"


def make_folder(product: str, company: str, date: str,
                base: Path = TARGET_3D) -> Path:
    """
    날짜_아이템명_업체명 형식으로 폴더 생성
    예) 260326_부품 2종_올로스코프
    """
    folder_name = f"{date}_{product}_{company}"
    dest = base / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    return dest
