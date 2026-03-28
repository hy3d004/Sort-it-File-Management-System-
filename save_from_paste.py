"""
에어테이블 행 붙여넣기 파서
에어테이블에서 복사한 행을 붙여넣으면 업체명/아이템명을 자동 추출하여 폴더를 생성합니다.

사용법:
  python save_from_paste.py          # 대화형으로 붙여넣기
  python save_from_paste.py --detect # 컬럼 구조 자동 탐지 후 출력
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from utils import check_drive, make_folder, EXT_ICONS

# ──────────────────────────────────────────────
# ✏️  컬럼 위치 설정 (0부터 시작)
#     에어테이블 테이블 구조에 맞게 수정하세요
# ──────────────────────────────────────────────
COL_DATE    = 1   # 날짜 (예: 2026-03-26 17:23)
COL_COMPANY = 5   # 업체명
COL_PRODUCT = 8   # 아이템명/제품명
# ──────────────────────────────────────────────


def parse_row(raw: str) -> dict:
    """탭으로 구분된 에어테이블 행 파싱"""
    cols = raw.strip().split("\t")
    
    def get_col(idx: int) -> str:
        if idx < len(cols):
            # 첨부파일 링크가 포함된 경우 파일명만 추출
            val = cols[idx].strip()
            if "(" in val and "http" in val:
                val = val.split("(")[0].strip()
            return val
        return ""

    company = get_col(COL_COMPANY)
    product = get_col(COL_PRODUCT)

    # 날짜 파싱: "2026-03-26 17:23" → "260326"
    date_str = get_col(COL_DATE)
    try:
        date = datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%y%m%d")
    except ValueError:
        date = datetime.today().strftime("%y%m%d")

    return {
        "company": company,
        "product": product,
        "date": date,
        "all_cols": cols,
    }


def detect_columns(raw: str):
    """컬럼 구조를 출력해서 사용자가 인덱스를 확인할 수 있도록 함"""
    cols = raw.strip().split("\t")
    print("\n📋 컬럼 구조 탐지 결과:")
    print("─" * 50)
    for i, col in enumerate(cols):
        val = col.strip()
        if len(val) > 40:
            val = val[:40] + "..."
        if val:
            print(f"  [{i:02d}]  {val}")
    print("─" * 50)
    print(f"\n현재 설정: 업체명={COL_COMPANY}, 아이템명={COL_PRODUCT}")
    print("변경이 필요하면 이 파일 상단의 COL_COMPANY, COL_PRODUCT 값을 수정하세요.\n")


def run_interactive():
    print("\n╔══════════════════════════════════════════╗")
    print("║   에어테이블 행 붙여넣기 → 폴더 자동 생성  ║")
    print("╚══════════════════════════════════════════╝")
    print("\n에어테이블에서 행을 복사한 뒤 아래에 붙여넣고 Enter를 두 번 누르세요:\n")

    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    raw = "\n".join(lines)
    if not raw.strip():
        print("❌ 입력된 내용이 없습니다.")
        sys.exit(1)

    process(raw)


def process(raw: str, move_files: bool = False):
    """파싱 후 폴더 생성 (Claude 에이전트 또는 대화형에서 호출)"""
    parsed = parse_row(raw)
    company = parsed["company"]
    product = parsed["product"]
    date    = parsed["date"]

    if not company or not product:
        print(f"ERROR:PARSE_FAILED:업체명='{company}', 아이템명='{product}'")
        print("  → COL_COMPANY, COL_PRODUCT 인덱스를 확인해주세요.")
        print("  → python save_from_paste.py --detect 으로 컬럼 구조를 확인하세요.")
        sys.exit(1)

    print(f"PARSED:날짜={date}, 업체명={company}, 아이템명={product}")

    # 드라이브 확인
    if not check_drive():
        print("ERROR:DRIVE_NOT_FOUND")
        sys.exit(1)

    # 폴더 생성
    dest = make_folder(product, company, date)
    print(f"FOLDER_CREATED:{dest.name}")
    print(f"DEST:{dest}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detect", action="store_true",
                        help="붙여넣은 행의 컬럼 구조 탐지")
    parser.add_argument("--paste", type=str,
                        help="행 텍스트를 직접 인자로 전달 (Claude 에이전트용)")
    args = parser.parse_args()

    if args.detect:
        print("붙여넣을 행을 입력하고 Enter를 두 번 누르세요:\n")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        detect_columns("\n".join(lines))

    elif args.paste:
        process(args.paste)

    else:
        run_interactive()


if __name__ == "__main__":
    main()
