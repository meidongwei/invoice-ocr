#!/usr/bin/env python3
"""发票识别桌面应用（PySide6）。"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from invoice_core import (
    CSV_FIELDS,
    INVOICE_SUFFIXES,
    get_default_output_dir,
    process_invoices,
)

APP_TITLE = "发票识别"

STATUS_STYLES = {
    "ready": ("#E8F5E9", "#1B5E20"),
    "running": ("#FFF3E0", "#E65100"),
    "success": ("#E3F2FD", "#0D47A1"),
    "error": ("#FFEBEE", "#B71C1C"),
}


def log(message: str) -> None:
    print(message, flush=True)


class RecognizeWorker(QObject):
    status = Signal(str)
    progress = Signal(int, int, str)
    finished = Signal(list, str)
    failed = Signal(str, str)

    def __init__(self, files: list[Path], output_dir: Path) -> None:
        super().__init__()
        self.files = files
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            rows, output_path = process_invoices(
                self.files,
                self.output_dir,
                on_progress=lambda c, t, n: self.progress.emit(c, t, n),
                on_status=lambda msg: self.status.emit(msg),
            )
            self.finished.emit(rows, str(output_path))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class InvoiceApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(960, 700)
        self.setMinimumSize(820, 640)

        self.selected_files: list[Path] = []
        self.output_dir = get_default_output_dir()
        self.last_output_path: Path | None = None
        self.is_running = False
        self._thread: QThread | None = None
        self._worker: RecognizeWorker | None = None

        self._build_ui()
        self._refresh_file_list()
        self._refresh_output_label()
        self._set_status("就绪。请选择发票文件，然后点击「开始识别」。", "ready")
        log("发票识别应用已启动（PySide6）。")

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        tip = QLabel("选择发票文件（PDF / 图片），点击开始识别，自动生成 CSV。")
        tip.setFont(QFont("", 13))
        root.addWidget(tip)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        self.status_label.setContentsMargins(12, 8, 12, 8)
        root.addWidget(self.status_label)

        # 文件区
        file_group = QGroupBox("发票文件")
        file_layout = QVBoxLayout(file_group)
        file_btn_row = QHBoxLayout()
        self.select_button = QPushButton("选择文件")
        self.select_button.clicked.connect(self._choose_files)
        self.clear_button = QPushButton("清空列表")
        self.clear_button.clicked.connect(self._clear_files)
        file_btn_row.addWidget(self.select_button)
        file_btn_row.addWidget(self.clear_button)
        file_btn_row.addStretch()
        file_layout.addLayout(file_btn_row)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(110)
        file_layout.addWidget(self.file_list)
        root.addWidget(file_group)

        # 输出目录
        out_group = QGroupBox("输出位置")
        out_layout = QHBoxLayout(out_group)
        self.output_label = QLabel("")
        self.output_label.setWordWrap(True)
        self.change_dir_button = QPushButton("更改目录")
        self.change_dir_button.clicked.connect(self._choose_output_dir)
        out_layout.addWidget(self.output_label, stretch=1)
        out_layout.addWidget(self.change_dir_button)
        root.addWidget(out_group)

        # 操作区
        action_row = QHBoxLayout()
        self.start_button = QPushButton("开始识别")
        self.start_button.setMinimumHeight(36)
        self.start_button.setStyleSheet(
            "QPushButton { background:#007AFF; color:white; font-weight:bold; padding:8px 18px; }"
            "QPushButton:disabled { background:#AAAAAA; color:white; }"
        )
        self.start_button.clicked.connect(self._start_recognition)

        self.open_folder_button = QPushButton("打开结果文件夹")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)

        self.progress = QProgressBar()
        self.progress.setMinimumWidth(240)
        self.progress.setValue(0)

        action_row.addWidget(self.start_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addStretch()
        action_row.addWidget(self.progress)
        root.addLayout(action_row)

        # 结果区
        result_group = QGroupBox("识别结果")
        result_layout = QVBoxLayout(result_group)
        self.result_table = QTableWidget(0, len(CSV_FIELDS))
        self.result_table.setHorizontalHeaderLabels(CSV_FIELDS)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        # 源文件 / 发票类型 / 销售方名称 / 发票号码 / 合计税额
        widths = [160, 220, 220, 160, 90]
        for index, width in enumerate(widths):
            self.result_table.setColumnWidth(index, width)
        result_layout.addWidget(self.result_table)

        self.overlay = QLabel("")
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setStyleSheet(
            "background:#F2F2F7; border:1px solid #CCCCCC; font-size:15px; font-weight:bold;"
        )
        self.overlay.hide()
        result_layout.addWidget(self.overlay)
        root.addWidget(result_group, stretch=1)

        # 日志区
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(110)
        log_layout.addWidget(self.log_text)
        root.addWidget(log_group)

    def _append_log(self, message: str) -> None:
        log(message)
        self.log_text.append(message)

    def _set_status(self, message: str, kind: str = "ready") -> None:
        bg, fg = STATUS_STYLES.get(kind, STATUS_STYLES["ready"])
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"background:{bg}; color:{fg}; font-weight:bold; border-radius:4px;"
        )

    def _choose_files(self) -> None:
        if self.is_running:
            QMessageBox.information(self, APP_TITLE, "识别正在进行中，请等待完成。")
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择发票文件",
            "",
            "发票文件 (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;"
            "PDF (*.pdf);;"
            "图片 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;"
            "所有文件 (*.*)",
        )
        if not paths:
            return

        existing = {path.resolve() for path in self.selected_files}
        added = 0
        for raw_path in paths:
            path = Path(raw_path)
            if path.suffix.lower() not in INVOICE_SUFFIXES:
                continue
            resolved = path.resolve()
            if resolved not in existing:
                self.selected_files.append(path)
                existing.add(resolved)
                added += 1

        self._refresh_file_list()
        if added:
            message = f"已添加 {added} 个文件，共 {len(self.selected_files)} 个待识别。"
            self._set_status(message, "ready")
            self._append_log(message)

    def _clear_files(self) -> None:
        if self.is_running:
            QMessageBox.information(self, APP_TITLE, "识别正在进行中，请等待完成。")
            return
        self.selected_files.clear()
        self._refresh_file_list()
        self._clear_results()
        self._set_status("文件列表已清空。", "ready")
        self._append_log("文件列表已清空。")

    def _choose_output_dir(self) -> None:
        if self.is_running:
            QMessageBox.information(self, APP_TITLE, "识别正在进行中，请等待完成。")
            return
        chosen = QFileDialog.getExistingDirectory(
            self,
            "选择 CSV 输出目录",
            str(self.output_dir),
        )
        if chosen:
            self.output_dir = Path(chosen)
            self._refresh_output_label()
            self._append_log(f"输出目录已设置为：{self.output_dir}")

    def _refresh_file_list(self) -> None:
        self.file_list.clear()
        for path in self.selected_files:
            self.file_list.addItem(path.name)

    def _refresh_output_label(self) -> None:
        self.output_label.setText(str(self.output_dir))

    def _clear_results(self) -> None:
        self.result_table.setRowCount(0)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.select_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.change_dir_button.setEnabled(enabled)
        if enabled:
            self.start_button.setEnabled(True)
            self.start_button.setText("开始识别")
            self.open_folder_button.setEnabled(self.last_output_path is not None)
        else:
            self.start_button.setEnabled(False)
            self.start_button.setText("识别中…")
            self.open_folder_button.setEnabled(False)

    def _show_running_ui(self, total_files: int) -> None:
        self.is_running = True
        self._set_buttons_enabled(False)
        self._clear_results()
        self.progress.setMaximum(max(total_files, 1))
        self.progress.setValue(0)
        self._set_status(f"正在识别 0/{total_files}，请稍候…", "running")
        self.result_table.hide()
        self.overlay.setText(
            "正在识别，请稍候…\n\n首次识别图片时可能需要 30~60 秒\n请勿关闭窗口"
        )
        self.overlay.show()

    def _hide_running_ui(self) -> None:
        self.overlay.hide()
        self.result_table.show()
        self.is_running = False
        self._set_buttons_enabled(True)

    def _start_recognition(self) -> None:
        if self.is_running:
            QMessageBox.information(self, APP_TITLE, "识别正在进行中，请耐心等待。")
            return
        if not self.selected_files:
            QMessageBox.warning(self, APP_TITLE, "请先选择至少一个发票文件。")
            return

        total = len(self.selected_files)
        self._append_log(f"========== 开始识别 {total} 个文件 ==========")
        self._show_running_ui(total)

        self._thread = QThread(self)
        self._worker = RecognizeWorker(list(self.selected_files), self.output_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._handle_status)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_success)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()
        self._append_log("后台识别线程已启动。")

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _handle_status(self, message: str) -> None:
        self._append_log(message)
        self.overlay.setText(
            f"{message}\n\n首次识别图片时可能需要 30~60 秒\n请勿关闭窗口"
        )

    def _update_progress(self, current: int, total: int, filename: str) -> None:
        self.progress.setValue(current)
        message = f"正在识别 ({current}/{total})：{filename}"
        self._set_status(message, "running")
        self._append_log(message)
        self.overlay.setText(message)

    def _on_success(self, rows: list, output_path: str) -> None:
        path = Path(output_path)
        self._hide_running_ui()
        self._clear_results()
        self.result_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, field in enumerate(CSV_FIELDS):
                self.result_table.setItem(
                    row_index, col_index, QTableWidgetItem(str(row.get(field, "")))
                )

        self.last_output_path = path
        self.open_folder_button.setEnabled(True)
        self.progress.setValue(self.progress.maximum())

        message = f"识别完成，已生成：{path.name}"
        self._set_status(message, "success")
        self._append_log(message)
        self._append_log(f"CSV 保存路径：{path}")

        QMessageBox.information(
            self,
            APP_TITLE,
            f"识别完成！\n\n共处理 {len(rows)} 张发票\n文件已保存至：\n{path}",
        )

    def _on_error(self, message: str, detail: str = "") -> None:
        self._hide_running_ui()
        self._set_status(f"识别失败：{message}", "error")
        self._append_log(f"识别失败：{message}")
        if detail:
            self._append_log(detail)
            log(detail)
        QMessageBox.critical(self, APP_TITLE, f"识别过程中出现错误：\n\n{message}")

    def _open_output_folder(self) -> None:
        folder = self.last_output_path.parent if self.last_output_path else self.output_dir
        if not folder.exists():
            QMessageBox.warning(self, APP_TITLE, "输出目录不存在。")
            return
        if sys.platform == "win32":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = InvoiceApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
