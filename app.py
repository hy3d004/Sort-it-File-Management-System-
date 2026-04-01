"""
의뢰파일 폴더 생성 프로그램 (PyQt6)
에어테이블 행을 붙여넣고 파일을 추가하면 자동으로 폴더를 생성하고 파일을 복사합니다.
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QFrame,
    QGridLayout, QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QPixmap, QIcon, QFont

from utils import check_drive, make_folder, get_image_target, TARGET_3D, EXT_ICONS

# ── 설정 ──
COL_DATE = 1
COL_COMPANY = 5
COL_PRODUCT = 8

if getattr(sys, "frozen", False):
    BASEDIR = Path(sys._MEIPASS)
else:
    BASEDIR = Path(__file__).parent


# ═══════════════════════════════════════════════
#  커스텀 위젯
# ═══════════════════════════════════════════════

class PasteTextEdit(QTextEdit):
    """Ctrl+V 시 기존 텍스트를 지우고 새로 붙여넣는 텍스트 에디터"""
    def insertFromMimeData(self, source):
        self.clear()
        if source.hasText():
            self.setPlainText(source.text())


class CopyThread(QThread):
    """파일 복사를 백그라운드에서 수행"""
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object, list, list)

    def __init__(self, files, dest):
        super().__init__()
        self.files = files
        self.dest = dest

    def run(self):
        copied, errors = [], []
        for i, f in enumerate(self.files, 1):
            try:
                shutil.copy2(f, self.dest / f.name)
                copied.append(f.name)
            except Exception as e:
                errors.append(f"{f.name}: {e}")
            self.progress.emit(i, len(self.files))
        self.done.emit(self.dest, copied, errors)


class FileItemWidget(QFrame):
    """파일 목록의 개별 아이템"""
    removed = pyqtSignal(object)  # Path

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setObjectName("fileItem")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(7)

        # 확장자 뱃지
        ext = filepath.suffix.upper().lstrip(".")[:4]
        ext_lbl = QLabel(ext)
        ext_lbl.setObjectName("extBadge")
        ext_lbl.setFixedSize(32, 22)
        ext_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ext in ("STL", "OBJ", "3MF", "STP", "STEP"):
            ext_lbl.setProperty("ext3d", "true")

        # 파일명
        name_lbl = QLabel(filepath.name)
        name_lbl.setObjectName("fileName")

        # 크기
        try:
            sz = filepath.stat().st_size
            if sz >= 1048576:
                size_str = f"{sz / 1048576:.1f} MB"
            elif sz >= 1024:
                size_str = f"{sz // 1024} KB"
            else:
                size_str = f"{sz} B"
        except OSError:
            size_str = ""
        size_lbl = QLabel(size_str)
        size_lbl.setObjectName("fileSize")

        # 삭제
        del_btn = QPushButton("\u00d7")
        del_btn.setObjectName("fileDelBtn")
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self.removed.emit(self.filepath))

        layout.addWidget(ext_lbl)
        layout.addWidget(name_lbl, 1)
        layout.addWidget(size_lbl)
        layout.addWidget(del_btn)


class DropArea(QFrame):
    """드래그앤드롭 영역"""
    files_dropped = pyqtSignal(list)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)

        icon_frame = QFrame()
        icon_frame.setObjectName("dropIcon")
        icon_frame.setFixedSize(32, 32)
        il = QVBoxLayout(icon_frame)
        il.setContentsMargins(0, 0, 0, 0)
        arrow = QLabel("\u2193")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("font-size:16px; color:#2563eb; background:transparent; border:none;")
        il.addWidget(arrow)

        txt = QLabel("파일을 여기로 드래그하거나 클릭하여 추가")
        txt.setObjectName("dropText")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel("PNG \u00b7 JPG \u00b7 STL \u00b7 OBJ \u00b7 STEP 등")
        sub.setObjectName("dropSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_frame, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(txt)
        layout.addWidget(sub)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [
            Path(u.toLocalFile())
            for u in event.mimeData().urls()
            if Path(u.toLocalFile()).is_file()
        ]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, event):
        self.clicked.emit()


# ═══════════════════════════════════════════════
#  탭 (3D / 이미지 공통)
# ═══════════════════════════════════════════════

class FileTab(QWidget):
    status_changed = pyqtSignal(str, str)

    def __init__(self, target_base, btn_label, parent=None):
        super().__init__(parent)
        self.target_base = target_base
        self.btn_label = btn_label
        self.files = []
        self._worker = None
        self._build_ui()

    # ── UI 구성 ──
    def _build_ui(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(14, 14, 14, 12)
        ly.setSpacing(10)

        # 붙여넣기
        h = QHBoxLayout()
        h.addWidget(self._sec("에어테이블 행 붙여넣기"))
        h.addStretch()
        rst = QPushButton("초기화")
        rst.setObjectName("chipBtn")
        rst.setCursor(Qt.CursorShape.PointingHandCursor)
        rst.clicked.connect(self._reset)
        h.addWidget(rst)
        ly.addLayout(h)

        self.txt_paste = PasteTextEdit()
        self.txt_paste.setObjectName("pasteArea")
        self.txt_paste.setFixedHeight(58)
        self.txt_paste.setPlaceholderText(
            "에어테이블에서 행을 복사한 뒤 붙여넣으세요 (Ctrl+V)")
        self.txt_paste.textChanged.connect(self._do_parse)
        ly.addWidget(self.txt_paste)

        ly.addWidget(self._div())

        # 파싱 결과
        ly.addWidget(self._sec("파싱 결과"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.fields = {}
        for i, (label, key) in enumerate(
            [("날짜", "date"), ("업체명", "company"), ("아이템명", "product")]
        ):
            lbl = QLabel(label)
            lbl.setObjectName("parseKey")
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lbl.setFixedWidth(50)
            ent = QLineEdit()
            ent.setObjectName("parseValue")
            ent.setPlaceholderText("\u2014")
            ent.textChanged.connect(self._on_field_edit)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(ent, i, 1)
            self.fields[key] = ent
        ly.addLayout(grid)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setObjectName("folderPreview")
        ly.addWidget(self.lbl_preview)

        ly.addWidget(self._div())

        # 파일
        h2 = QHBoxLayout()
        h2.addWidget(self._sec("첨부 파일"))
        h2.addStretch()
        self.badge = QLabel("0")
        self.badge.setObjectName("badge")
        h2.addWidget(self.badge)
        ly.addLayout(h2)

        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        self.drop_area.clicked.connect(self._add_files)
        self.drop_area.setMinimumHeight(120)
        ly.addWidget(self.drop_area, 1)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setMinimumHeight(120)
        self.file_list.hide()
        ly.addWidget(self.file_list, 1)

        btn_row = QHBoxLayout()
        for text, name, slot in [
            ("+ 파일 추가", "btnSmall", self._add_files),
            ("선택 삭제", "btnSmallDel", self._remove_selected),
            ("전체 삭제", "btnSmallDel", self._clear_files),
        ]:
            b = QPushButton(text)
            b.setObjectName(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        ly.addLayout(btn_row)

        # CTA
        self.btn_cta = QPushButton(self.btn_label)
        self.btn_cta.setObjectName("ctaBtn")
        self.btn_cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cta.clicked.connect(self._create_folder)
        ly.addWidget(self.btn_cta)

    @staticmethod
    def _sec(text):
        lbl = QLabel(text.upper())
        lbl.setObjectName("sectionLabel")
        return lbl

    @staticmethod
    def _div():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("divider")
        return line

    def _status(self, msg, t=""):
        self.status_changed.emit(msg, t)

    # ── 파싱 ──
    def _do_parse(self):
        raw = self.txt_paste.toPlainText().strip()
        if not raw:
            return
        cols = raw.split("\t")
        need = max(COL_DATE, COL_COMPANY, COL_PRODUCT) + 1
        if len(cols) < need:
            self._status(f"탭 구분 컬럼 부족 ({len(cols)}개/{need}개 필요)")
            return

        def clean(idx):
            val = cols[idx].strip()
            if "(" in val and "http" in val:
                val = val.split("(")[0].strip()
            return val

        company, product = clean(COL_COMPANY), clean(COL_PRODUCT)
        try:
            date = datetime.strptime(
                clean(COL_DATE)[:10], "%Y-%m-%d"
            ).strftime("%y%m%d")
        except ValueError:
            date = datetime.today().strftime("%y%m%d")

        if not company or not product:
            return

        for key, val in [
            ("date", date), ("company", company), ("product", product)
        ]:
            f = self.fields[key]
            f.blockSignals(True)
            f.setText(val)
            f.setProperty("filled", "true")
            f.style().unpolish(f)
            f.style().polish(f)
            f.blockSignals(False)

        self.lbl_preview.setText(f"\u2192  {date}_{product}_{company}")
        self._status(f"파싱 완료: {date}_{product}_{company}", "on")

    def _on_field_edit(self):
        d = self.fields["date"].text().strip()
        c = self.fields["company"].text().strip()
        p = self.fields["product"].text().strip()
        if d and c and p:
            self.lbl_preview.setText(f"\u2192  {d}_{p}_{c}")

    # ── 파일 관리 ──
    def _on_files_dropped(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._refresh_files()
        self._status(f"파일 {len(self.files)}개 추가됨", "on")

    def _add_files(self):
        desktop = Path(os.path.expanduser("~/Desktop"))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "파일 선택", str(desktop)
        )
        for p in paths:
            path = Path(p)
            if path not in self.files:
                self.files.append(path)
        if paths:
            self._refresh_files()
            self._status(f"파일 {len(self.files)}개 추가됨", "on")

    def _remove_selected(self):
        items = self.file_list.selectedItems()
        if not items:
            return
        rows = sorted(
            [self.file_list.row(it) for it in items], reverse=True
        )
        for r in rows:
            del self.files[r]
        self._refresh_files()

    def _remove_file(self, filepath):
        if filepath in self.files:
            self.files.remove(filepath)
            self._refresh_files()

    def _clear_files(self):
        self.files.clear()
        self._refresh_files()
        self._status("전체 삭제됨")

    def _refresh_files(self):
        self.file_list.clear()
        self.badge.setText(str(len(self.files)))
        if not self.files:
            self.drop_area.show()
            self.file_list.hide()
            return
        self.drop_area.hide()
        self.file_list.show()
        for f in self.files:
            w = FileItemWidget(f)
            w.removed.connect(self._remove_file)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 34))
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, w)

    # ── 폴더 생성 ──
    def _create_folder(self):
        d = self.fields["date"].text().strip()
        c = self.fields["company"].text().strip()
        p = self.fields["product"].text().strip()

        if not d or not c or not p:
            QMessageBox.warning(
                self, "알림", "날짜, 업체명, 아이템명을 모두 입력하세요."
            )
            return
        if not check_drive(self.target_base):
            QMessageBox.critical(
                self, "오류",
                f"드라이브에 접근할 수 없습니다.\n경로: {self.target_base}",
            )
            return

        self.btn_cta.setEnabled(False)
        dest = make_folder(p, c, d, self.target_base)

        if not self.files:
            QMessageBox.information(
                self, "완료",
                f"폴더: {dest.name}\n\n(첨부 파일 없이 폴더만 생성)",
            )
            self._status(f"\u2713 완료: {dest.name}", "ok")
            self.btn_cta.setEnabled(True)
            self._reset()
            return

        self._status("파일 복사 중...", "on")
        self._worker = CopyThread(list(self.files), dest)
        self._worker.progress.connect(
            lambda i, t: self._status(f"파일 복사 중... ({i}/{t})", "on")
        )
        self._worker.done.connect(self._copy_done)
        self._worker.start()

    def _copy_done(self, dest, copied, errors):
        self.btn_cta.setEnabled(True)
        msg = f"폴더: {dest.name}\n"
        if copied:
            msg += f"\n저장된 파일 {len(copied)}개:\n"
            for name in copied:
                icon = EXT_ICONS.get(Path(name).suffix.lower(), "")
                msg += f"  {icon} {name}\n"
        if errors:
            msg += f"\n오류 {len(errors)}개:\n"
            for e in errors:
                msg += f"  \u2716 {e}\n"
        QMessageBox.information(self, "완료", msg)
        self._status(f"\u2713 완료: {dest.name}", "ok")
        self._reset()

    def _reset(self):
        self.txt_paste.clear()
        for ent in self.fields.values():
            ent.clear()
            ent.setProperty("filled", "false")
            ent.style().unpolish(ent)
            ent.style().polish(ent)
        self.lbl_preview.setText("")
        self.files.clear()
        self._refresh_files()


# ═══════════════════════════════════════════════
#  메인 윈도우
# ═══════════════════════════════════════════════

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sort it [폴더 생성 프로그램]")
        self.setFixedSize(440, 740)

        # 윈도우 아이콘
        icon_path = BASEDIR / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 탭 헤더 ──
        tab_bar = QFrame()
        tab_bar.setObjectName("tabBar")
        tl = QHBoxLayout(tab_bar)
        tl.setContentsMargins(14, 0, 14, 0)
        tl.setSpacing(0)

        self.tab_btns = []
        for i, text in enumerate(["3D 파일", "이미지"]):
            btn = QPushButton(text)
            btn.setObjectName("tabBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self.tab_btns.append(btn)
            tl.addWidget(btn)

        tl.addStretch()

        # 로고
        logo_lbl = QLabel()
        logo_loaded = False
        for ext in ("png", "jpg", "jpeg"):
            lp = BASEDIR / "assets" / f"logo.{ext}"
            if lp.exists():
                pm = QPixmap(str(lp))
                if not pm.isNull():
                    logo_lbl.setPixmap(
                        pm.scaledToHeight(
                            20, Qt.TransformationMode.SmoothTransformation
                        )
                    )
                    logo_loaded = True
                    break
        if not logo_loaded:
            logo_lbl.setText("한양3D팩토리")
            logo_lbl.setStyleSheet(
                "color:#8ab4d8; font-size:11px; font-weight:bold;"
            )
        tl.addWidget(logo_lbl)
        root.addWidget(tab_bar)

        # ── 콘텐츠 ──
        self.stack = QStackedWidget()
        tab_3d = FileTab(TARGET_3D, "3D파일 폴더 생성 및 저장")
        tab_img = FileTab(get_image_target(), "이미지폴더 생성 및 저장")
        tab_3d.status_changed.connect(self._update_status)
        tab_img.status_changed.connect(self._update_status)
        self.stack.addWidget(tab_3d)
        self.stack.addWidget(tab_img)
        root.addWidget(self.stack, 1)

        # ── 상태 바 ──
        sbar = QFrame()
        sbar.setObjectName("statusBar")
        sl = QHBoxLayout(sbar)
        sl.setContentsMargins(14, 5, 14, 5)
        self.s_dot = QLabel("\u25cf")
        self.s_dot.setObjectName("sDot")
        self.s_txt = QLabel("대기 중")
        self.s_txt.setObjectName("sTxt")
        ver = QLabel("v2.1")
        ver.setObjectName("sVer")
        sl.addWidget(self.s_dot)
        sl.addWidget(self.s_txt)
        sl.addStretch()
        sl.addWidget(ver)
        root.addWidget(sbar)

        self._center()

    def _switch_tab(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.tab_btns):
            b.setChecked(i == idx)

    def _update_status(self, msg, stype):
        self.s_txt.setText(msg)
        c = "#22c55e" if stype in ("on", "ok") else "#243040"
        self.s_dot.setStyleSheet(f"color:{c}; font-size:8px;")

    def _center(self):
        s = QApplication.primaryScreen().geometry()
        self.move(
            (s.width() - self.width()) // 2,
            (s.height() - self.height()) // 2,
        )


# ═══════════════════════════════════════════════
#  스타일시트 (QSS)
# ═══════════════════════════════════════════════

QSS = """
* { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; font-size: 12px; }

QMainWindow { background: #f4f5f7; }

/* ── 탭 바 ── */
#tabBar {
    background: #1c2d47;
    border-bottom: 1px solid #0e1828;
    min-height: 36px;
}
#tabBtn {
    background: transparent; color: #3a5070; border: none;
    padding: 8px 16px; font-size: 12px;
}
#tabBtn:checked {
    color: #e8eef5; font-weight: bold;
    border-bottom: 2px solid #4a8ef0;
}
#tabBtn:hover:!checked { color: #6a90b8; }

/* ── 섹션 라벨 ── */
#sectionLabel {
    font-size: 10px; font-weight: bold;
    color: #8898b0; letter-spacing: 1px;
}

/* ── 붙여넣기 영역 ── */
#pasteArea {
    border: 1px solid #d4dae6; border-radius: 6px;
    background: white; font-size: 12px; color: #1e2535;
    padding: 8px 10px;
    font-family: Consolas, 'Malgun Gothic';
}
#pasteArea:focus { border-color: #4a8ef0; }

/* ── 초기화 버튼 ── */
#chipBtn {
    font-size: 10px; font-weight: 500;
    padding: 3px 10px; border: 1px solid #d4dae6;
    border-radius: 12px; background: white; color: #6a7a90;
}
#chipBtn:hover {
    border-color: #4a8ef0; color: #2563eb; background: #eff6ff;
}

/* ── 파싱 결과 ── */
#parseKey { font-size: 11px; color: #8898b0; }
#parseValue {
    border: 1px solid #d4dae6; border-radius: 5px;
    padding: 5px 9px; font-size: 12px;
    background: #f8f9fc; color: #8898b0;
}
#parseValue[filled="true"] {
    background: #eff6ff; border-color: #bfd8f8;
    color: #1a52c0; font-weight: bold;
}
#folderPreview {
    font-size: 10px; color: #9ca3b0;
    font-family: Consolas; margin-top: 2px;
}

/* ── 뱃지 ── */
#badge {
    background: #dbeafe; color: #1d4ed8;
    font-size: 9px; font-weight: bold;
    padding: 1px 7px; border-radius: 10px;
    max-height: 16px;
}

/* ── 드롭 영역 ── */
#dropArea {
    border: 1.5px dashed #ccd5e4; border-radius: 8px;
    min-height: 96px; background: #f8f9fc;
}
#dropArea:hover { border-color: #4a8ef0; background: #eff6ff; }
#dropIcon { background: #deeafc; border-radius: 8px; }
#dropText {
    font-size: 11px; color: #8898b0;
    background: transparent; border: none;
}
#dropSub {
    font-size: 10px; color: #b0bece;
    background: transparent; border: none;
}

/* ── 파일 리스트 ── */
#fileList {
    border: 1px solid #e4eaf4; border-radius: 6px;
    background: white; outline: none;
}
#fileList::item {
    padding: 0; border-bottom: 1px solid #f0f2f7;
}
#fileList::item:selected { background: #eff6ff; }

#fileItem { background: transparent; border: none; }
#fileItem:hover { background: #f4f7ff; }

#extBadge {
    background: #dbeafe; color: #1d4ed8;
    font-size: 8px; font-weight: bold; border-radius: 4px;
}
#extBadge[ext3d="true"] { background: #dcfce7; color: #166534; }

#fileName {
    font-size: 11px; color: #374151;
    background: transparent; border: none;
}
#fileSize {
    font-size: 10px; color: #a0aec0;
    background: transparent; border: none;
}
#fileDelBtn {
    background: transparent; border: none;
    color: #d1d5db; font-size: 14px; border-radius: 4px;
}
#fileDelBtn:hover { color: #ef4444; background: #fef2f2; }

/* ── 작은 버튼 ── */
#btnSmall, #btnSmallDel {
    padding: 5px; border: 1px solid #d4dae6; border-radius: 5px;
    background: white; color: #6a7a90;
    font-size: 11px; font-weight: 500;
}
#btnSmall:hover {
    background: #f0f6ff; border-color: #93c5fd; color: #2563eb;
}
#btnSmallDel:hover {
    background: #fff5f5; border-color: #fca5a5; color: #dc2626;
}

/* ── CTA 버튼 ── */
#ctaBtn {
    background: #152040; border: none; border-radius: 7px;
    color: #c8daf0; font-size: 13px; font-weight: bold;
    padding: 11px;
}
#ctaBtn:hover { background: #1d3060; }
#ctaBtn:pressed { background: #0e1828; }
#ctaBtn:disabled { background: #374151; color: #6b7280; }

/* ── 구분선 ── */
#divider {
    border: none; border-top: 1px solid #e4e8f0;
    max-height: 1px; margin: 2px 0;
}

/* ── 상태 바 ── */
#statusBar {
    background: #0e1828; border-top: 1px solid #0a1018;
}
#sDot { font-size: 8px; color: #243040; }
#sTxt { font-size: 10px; color: #3a5070; }
#sVer { font-size: 10px; color: #243040; }

/* ── 스크롤바 ── */
QScrollBar:vertical {
    width: 6px; background: transparent;
}
QScrollBar::handle:vertical {
    background: #c4cad6; border-radius: 3px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


# ═══════════════════════════════════════════════
#  실행
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = App()
    window.show()
    sys.exit(app.exec())
