from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QTime, QTimer, QUrl
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QSystemTrayIcon,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .config import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    RU_WEEKDAYS_FULL,
    RU_WEEKDAYS_SHORT,
    Settings,
    app_data_dir,
    format_human_datetime,
    is_autostart_enabled,
    load_settings,
    log_file,
    save_settings,
    set_autostart,
)
from .printing import (
    PrintTask,
    available_printers,
    default_printer_name,
    validate_print_setup,
)
from .scheduler import Scheduler, is_due, next_occurrence

LOGGER = logging.getLogger(__name__)

FILE_FILTER = (
    "Документы и изображения "
    "(*.pdf *.txt *.md *.markdown *.html *.htm *.log *.csv "
    "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp "
    "*.doc *.docx *.rtf *.odt *.xls *.xlsx *.ods *.ppt *.pptx *.odp);;"
    "PDF (*.pdf);;"
    "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
    "Текст, HTML и Markdown (*.txt *.log *.csv *.html *.htm *.md *.markdown);;"
    "Все файлы (*.*)"
)

STYLE_SHEET = """
QMainWindow, QWidget {
    background-color: #f4f6fb;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dfe5ef;
    border-radius: 12px;
    margin-top: 13px;
    padding: 16px 14px 13px 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 13px;
    padding: 0 5px;
    color: #44536b;
    background-color: #f4f6fb;
}
QLabel {
    background: transparent;
}
QLineEdit, QComboBox, QTimeEdit {
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 20px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QComboBox:focus, QTimeEdit:focus {
    border: 1px solid #2563eb;
}
QLineEdit:disabled, QComboBox:disabled, QTimeEdit:disabled {
    background: #f4f6f9;
    color: #9aa7b8;
}
QComboBox {
    padding-right: 26px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #dfe5ef;
    selection-background-color: #e8efff;
    selection-color: #172033;
    padding: 4px;
    outline: 0;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    color: #25324a;
}
QPushButton:hover {
    background: #f3f6fc;
    border-color: #aebdd3;
}
QPushButton:pressed {
    background: #e8eef9;
}
QPushButton:disabled {
    color: #9aa7b8;
    background: #f4f6f9;
    border-color: #e4e9f1;
}
QPushButton#primary {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#primary:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}
QPushButton#primary:pressed {
    background: #1e40af;
}
QPushButton#primary:disabled {
    background: #9db9f5;
    border-color: #9db9f5;
    color: #ffffff;
}
QPushButton#day {
    background: #f7f9fc;
    border: 1px solid #d8e0ec;
    border-radius: 8px;
    padding: 6px 4px;
    min-width: 34px;
    color: #4a5a73;
}
QPushButton#day:hover {
    background: #eef4ff;
    border-color: #a9bce0;
}
QPushButton#day:checked {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#link {
    border: none;
    background: transparent;
    color: #2563eb;
    padding: 4px 5px;
    font-weight: 600;
}
QPushButton#link:hover {
    background: #e8efff;
    border-radius: 6px;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
    font-weight: 400;
}
QPlainTextEdit#log {
    background: #0f172a;
    color: #dbe7ff;
    border: 1px solid #1e293b;
    border-radius: 9px;
    padding: 8px;
    font-family: "Consolas";
    font-size: 9pt;
    selection-background-color: #315aab;
}
QFrame#footer {
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
}
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #edf1f7;
    color: #64748b;
    font-size: 9pt;
}
QStatusBar::item {
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #c7d2e3;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #aebdd3;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QToolTip {
    background: #172033;
    color: #ffffff;
    border: none;
    padding: 5px 7px;
}
QMenu {
    background: #ffffff;
    border: 1px solid #dfe5ef;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #e8efff;
    color: #172033;
}
"""


def make_app_icon() -> QIcon:
    """Рисует иконку без внешних файлов — она всегда доступна в exe."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor("#2563eb"))
        painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)

        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(
            QRectF(size * 0.27, size * 0.16, size * 0.46, size * 0.20),
            size * 0.035,
            size * 0.035,
        )
        painter.drawRoundedRect(
            QRectF(size * 0.16, size * 0.38, size * 0.68, size * 0.28),
            size * 0.07,
            size * 0.07,
        )

        painter.setBrush(QColor("#bfdbfe"))
        painter.drawRoundedRect(
            QRectF(size * 0.29, size * 0.59, size * 0.42, size * 0.25),
            size * 0.03,
            size * 0.03,
        )
        painter.setBrush(QColor("#2563eb"))
        painter.drawRoundedRect(
            QRectF(size * 0.36, size * 0.66, size * 0.28, size * 0.025),
            size * 0.01,
            size * 0.01,
        )
        painter.drawRoundedRect(
            QRectF(size * 0.36, size * 0.72, size * 0.20, size * 0.025),
            size * 0.01,
            size * 0.01,
        )
        painter.setBrush(QColor("#93c5fd"))
        painter.drawEllipse(
            QRectF(size * 0.70, size * 0.44, size * 0.055, size * 0.055)
        )
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class MainWindow(QMainWindow):
    def __init__(
        self,
        start_minimized: bool = False,
        local_server: QLocalServer | None = None,
    ) -> None:
        super().__init__()
        self.settings = load_settings()
        self._start_minimized = start_minimized
        self._local_server = local_server
        self._loading = True
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._persist)

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._refresh_time_labels)
        self._clock_timer.start()

        self._worker: PrintTask | None = None
        self._pending_schedule = False
        self._quit_requested = False
        self._quitting = False
        self._tray_hint_shown = False
        self._app_icon = make_app_icon()

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(self._app_icon)
        self.setAcceptDrops(True)
        self.setMinimumSize(660, 560)

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = 840
        height = 900
        if available:
            height = min(height, max(600, available.height() - 70))
        self.resize(width, height)

        self._build_ui()
        self._load_ui_values()
        self._setup_signals()
        self._setup_tray()
        self._setup_scheduler()

        self._loading = False
        self._refresh_document_info()
        self._refresh_printer_hint()
        self._refresh_time_labels()
        self._update_header_status()
        self._sync_tray()

        self._append_log(
            f"{APP_DISPLAY_NAME} {APP_VERSION} запущен. Настройки: {app_data_dir()}"
        )
        LOGGER.info("Приложение запущено")

        if self._local_server is not None:
            self._local_server.newConnection.connect(self._accept_instance_connection)
            QTimer.singleShot(0, self._accept_instance_connection)

        self._apply_startup_visibility()

    # ------------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 14)
        layout.setSpacing(13)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_document_group())
        layout.addWidget(self._build_printer_group())
        layout.addWidget(self._build_schedule_group())
        layout.addWidget(self._build_behavior_group())
        layout.addWidget(self._build_log_group())
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_footer())

        self.setCentralWidget(central)

        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        auto_label = QLabel("Автосохранение включено")
        auto_label.setStyleSheet("color: #7b8799; padding-right: 10px;")
        status.addPermanentWidget(auto_label)
        status.showMessage("Готово")

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(13)

        icon_label = QLabel()
        icon_label.setPixmap(self._app_icon.pixmap(52, 52))
        icon_label.setFixedSize(54, 54)
        icon_label.setScaledContents(True)
        header.addWidget(icon_label)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel(APP_DISPLAY_NAME)
        title_font = QFont("Segoe UI", 19)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet("color: #152033;")
        subtitle = QLabel("Автоматическая печать документа по дням недели")
        subtitle.setStyleSheet("color: #69778c; font-size: 9.5pt;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        self.status_pill = QLabel("Расписание выключено")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        header.addWidget(self.status_pill, 0, Qt.AlignmentFlag.AlignTop)
        return header

    def _build_document_group(self) -> QGroupBox:
        group = QGroupBox("Документ")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.document_edit = QLineEdit()
        self.document_edit.setPlaceholderText(
            "Путь к документу, например C:\\Документы\\отчёт.pdf"
        )
        self.document_edit.setClearButtonEnabled(True)
        self.browse_button = QPushButton("Обзор…")
        self.browse_button.setMinimumWidth(96)
        row.addWidget(self.document_edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)

        self.document_info = QLabel("Файл не выбран")
        self.document_info.setWordWrap(True)
        self.document_info.setStyleSheet("color: #718096; font-size: 9pt;")
        layout.addWidget(self.document_info)
        return group

    def _build_printer_group(self) -> QGroupBox:
        group = QGroupBox("Принтер")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.printer_combo = QComboBox()
        self.printer_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.printer_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.printer_combo.setMinimumContentsLength(20)
        self.refresh_button = QPushButton("Обновить список")
        self.refresh_button.setMinimumWidth(132)
        row.addWidget(self.printer_combo, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)

        self.printer_hint = QLabel("")
        self.printer_hint.setWordWrap(True)
        self.printer_hint.setStyleSheet("color: #718096; font-size: 9pt;")
        layout.addWidget(self.printer_hint)
        return group

    def _build_schedule_group(self) -> QGroupBox:
        group = QGroupBox("Расписание")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        top = QGridLayout()
        top.setHorizontalSpacing(10)
        top.setVerticalSpacing(8)
        top.addWidget(QLabel("Время печати"), 0, 0)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(9, 0))
        self.time_edit.setFixedWidth(112)
        top.addWidget(self.time_edit, 0, 1)
        top.setColumnStretch(2, 1)

        self.schedule_check = QCheckBox("Печать по расписанию")
        top.addWidget(self.schedule_check, 0, 3)

        top.addWidget(QLabel("Дни недели"), 1, 0)
        days_row = QHBoxLayout()
        days_row.setSpacing(6)
        self.day_buttons: list[QPushButton] = []
        for index, short_name in enumerate(RU_WEEKDAYS_SHORT):
            button = QPushButton(short_name)
            button.setObjectName("day")
            button.setCheckable(True)
            button.setFixedSize(48, 34)
            button.setToolTip(RU_WEEKDAYS_FULL[index])
            button.setAccessibleName(RU_WEEKDAYS_FULL[index])
            days_row.addWidget(button)
            self.day_buttons.append(button)
        days_row.addStretch(1)

        self.workdays_button = QPushButton("Будни")
        self.workdays_button.setObjectName("link")
        self.all_days_button = QPushButton("Все")
        self.all_days_button.setObjectName("link")
        days_row.addWidget(self.workdays_button)
        days_row.addWidget(self.all_days_button)
        top.addLayout(days_row, 1, 1, 1, 3)
        layout.addLayout(top)

        self.next_run_label = QLabel("")
        self.next_run_label.setWordWrap(True)
        self.next_run_label.setStyleSheet(
            "color: #334155; font-weight: 600; font-size: 9.5pt;"
        )
        layout.addWidget(self.next_run_label)

        note = QLabel(
            "Время и день недели берутся с системных часов компьютера. "
            "Если ПК был выключен, печать выполнится при запуске в течение "
            "5 минут после назначенного времени."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7b8799; font-size: 9pt; font-weight: 400;")
        layout.addWidget(note)
        return group

    def _build_behavior_group(self) -> QGroupBox:
        group = QGroupBox("Запуск и фон")
        layout = QVBoxLayout(group)
        layout.setSpacing(7)

        self.autostart_check = QCheckBox("Добавить приложение в автозагрузку Windows")
        self.tray_check = QCheckBox("Сворачивать в трей при закрытии окна")
        layout.addWidget(self.autostart_check)
        layout.addWidget(self.tray_check)

        self.autostart_hint = QLabel(
            "При автозапуске приложение откроется в трее и продолжит "
            "печать по расписанию."
        )
        self.autostart_hint.setWordWrap(True)
        self.autostart_hint.setStyleSheet(
            "color: #7b8799; font-size: 9pt; font-weight: 400;"
        )
        layout.addWidget(self.autostart_hint)

        if os.name != "nt":
            self.autostart_check.setEnabled(False)
            self.autostart_check.setToolTip(
                "Автозагрузка через реестр доступна только в Windows."
            )
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Журнал")
        layout = QVBoxLayout(group)
        layout.setSpacing(7)

        head = QHBoxLayout()
        head.addStretch(1)
        clear_button = QPushButton("Очистить окно")
        clear_button.setObjectName("link")
        clear_button.clicked.connect(self._clear_log)
        open_log_button = QPushButton("Открыть файл журнала")
        open_log_button.setObjectName("link")
        open_log_button.clicked.connect(self._open_log_file)
        head.addWidget(open_log_button)
        head.addWidget(clear_button)
        layout.addLayout(head)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setMinimumHeight(118)
        self.log_view.setMaximumHeight(160)
        self.log_view.setPlaceholderText("Здесь появятся события печати.")
        layout.addWidget(self.log_view)
        return group

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(22, 10, 22, 10)
        layout.setSpacing(8)

        hint = QLabel("Изменения сохраняются автоматически")
        hint.setStyleSheet("color: #7b8799; font-size: 9pt;")
        layout.addWidget(hint)
        layout.addStretch(1)

        open_folder_button = QPushButton("Папка настроек")
        open_folder_button.clicked.connect(self._open_settings_folder)
        layout.addWidget(open_folder_button)

        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.clicked.connect(self._save_clicked)
        layout.addWidget(self.save_button)

        self.print_button = QPushButton("Печать сейчас")
        self.print_button.setObjectName("primary")
        self.print_button.setMinimumWidth(136)
        self.print_button.clicked.connect(self._print_now)
        layout.addWidget(self.print_button)
        return footer

    # ------------------------------------------------------------------
    # Загрузка и сохранение
    # ------------------------------------------------------------------
    def _load_ui_values(self) -> None:
        settings = self.settings
        self.document_edit.setText(settings.document_path)
        self._refresh_printers(settings.printer_name)

        selected_days = set(settings.normalized_weekdays())
        for index, button in enumerate(self.day_buttons):
            button.setChecked(index in selected_days)

        parsed_time = QTime.fromString(settings.print_time, "HH:mm")
        self.time_edit.setTime(parsed_time if parsed_time.isValid() else QTime(9, 0))
        self.schedule_check.setChecked(settings.enabled)
        self.tray_check.setChecked(settings.minimize_to_tray)

        try:
            actual_autostart = is_autostart_enabled()
        except OSError as exc:
            LOGGER.warning("Не удалось проверить автозагрузку: %s", exc)
            actual_autostart = settings.autostart
        self.settings.autostart = actual_autostart
        self.autostart_check.setChecked(actual_autostart)

    def _setup_signals(self) -> None:
        self.document_edit.textChanged.connect(self._on_document_changed)
        self.browse_button.clicked.connect(self._browse_document)
        self.printer_combo.currentIndexChanged.connect(self._on_printer_changed)
        self.refresh_button.clicked.connect(self._refresh_printers_clicked)
        self.time_edit.timeChanged.connect(self._on_schedule_control_changed)
        self.schedule_check.toggled.connect(self._on_schedule_toggled)
        self.tray_check.toggled.connect(self._on_settings_changed)
        self.autostart_check.toggled.connect(self._on_autostart_toggled)
        for button in self.day_buttons:
            button.toggled.connect(self._on_schedule_control_changed)
        self.workdays_button.clicked.connect(lambda: self._set_weekdays(range(5)))
        self.all_days_button.clicked.connect(lambda: self._set_weekdays(range(7)))

    def _ui_settings(self) -> Settings:
        path = self.document_edit.text().strip().strip('"')
        printer = self.printer_combo.currentData() or ""
        weekdays = [
            index for index, button in enumerate(self.day_buttons) if button.isChecked()
        ]
        result = Settings(
            document_path=path,
            printer_name=str(printer),
            weekdays=weekdays,
            print_time=self.time_edit.time().toString("HH:mm"),
            enabled=self.schedule_check.isChecked(),
            autostart=self.autostart_check.isChecked(),
            minimize_to_tray=self.tray_check.isChecked(),
            last_triggered_date=self.settings.last_triggered_date,
        )
        result.normalize()
        return result

    def _persist(self, show_status: bool = False) -> bool:
        if self._loading:
            return True
        self._save_timer.stop()
        settings = self._ui_settings()
        self.settings = settings
        try:
            save_settings(settings)
        except OSError as exc:
            LOGGER.exception("Не удалось сохранить настройки")
            self._append_log(f"Не удалось сохранить настройки: {exc}")
            self.statusBar().showMessage("Ошибка сохранения настроек", 6000)
            if show_status:
                QMessageBox.critical(
                    self,
                    "Ошибка сохранения",
                    f"Не удалось сохранить настройки:\n{exc}",
                )
            return False

        self._scheduler.update_settings(settings)
        self._refresh_time_labels()
        self._update_header_status()
        self._sync_tray()
        self._refresh_document_info()
        self._refresh_printer_hint()
        if show_status:
            self.statusBar().showMessage("Настройки сохранены", 4000)
            self._append_log("Настройки сохранены.")
        return True

    def _schedule_persist(self) -> None:
        if not self._loading:
            self._save_timer.start()

    def _on_settings_changed(self) -> None:
        self._schedule_persist()
        self._update_header_status()
        self._update_next_run_label()
        self._sync_tray()

    def _on_document_changed(self) -> None:
        self._refresh_document_info()
        self._on_settings_changed()

    def _on_printer_changed(self) -> None:
        self._refresh_printer_hint()
        self._on_settings_changed()

    def _on_schedule_control_changed(self) -> None:
        if self._loading:
            return
        self._on_settings_changed()

    def _on_schedule_toggled(self, enabled: bool) -> None:
        if self._loading:
            return
        self._append_log("Расписание включено." if enabled else "Расписание выключено.")
        self._schedule_persist()
        self._refresh_time_labels()
        self._update_header_status()
        self._sync_tray()

    def _on_autostart_toggled(self, enabled: bool) -> None:
        if self._loading:
            return
        try:
            set_autostart(enabled)
        except OSError as exc:
            LOGGER.exception("Не удалось изменить автозагрузку")
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(not enabled)
            self.autostart_check.blockSignals(False)
            QMessageBox.critical(
                self,
                "Автозагрузка",
                f"Не удалось изменить автозагрузку Windows:\n{exc}",
            )
            return

        self._append_log(
            "Приложение добавлено в автозагрузку Windows."
            if enabled
            else "Приложение удалено из автозагрузки Windows."
        )
        self._save_timer.start(0)

    def _save_clicked(self) -> None:
        self._persist(show_status=True)

    # ------------------------------------------------------------------
    # Вспомогательные действия
    # ------------------------------------------------------------------
    def _browse_document(self) -> None:
        current = self.document_edit.text().strip().strip('"')
        start = str(Path(current).parent) if current else str(Path.home())
        if not Path(start).is_dir():
            start = str(Path.home())
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ для печати",
            start,
            FILE_FILTER,
        )
        if filename:
            self.document_edit.setText(filename)
            self._append_log(f"Выбран документ: {filename}")

    def _refresh_printers_clicked(self) -> None:
        self._refresh_printers(self._ui_settings().printer_name)
        self._on_settings_changed()
        self._append_log("Список принтеров обновлён.")

    def _refresh_printers(
        self,
        preferred: str = "",
    ) -> None:
        printers = available_printers()
        default_name = default_printer_name()

        self.printer_combo.blockSignals(True)
        self.printer_combo.clear()
        if not printers:
            self.printer_combo.addItem("Принтеры не найдены", "")
            if preferred:
                self.printer_combo.addItem(
                    f"{preferred}  (недоступен)", preferred
                )
                self.printer_combo.setCurrentIndex(1)
        else:
            for name in printers:
                label = name
                if name == default_name:
                    label = f"{name}  (по умолчанию)"
                self.printer_combo.addItem(label, name)

            if preferred and preferred not in printers:
                self.printer_combo.addItem(f"{preferred}  (недоступен)", preferred)

            wanted = preferred or default_name
            index = self.printer_combo.findData(wanted)
            index = max(index, 0)
            self.printer_combo.setCurrentIndex(index)
        self.printer_combo.blockSignals(False)
        self._refresh_printer_hint()

    def _refresh_document_info(self) -> None:
        raw = self.document_edit.text().strip().strip('"')
        if not raw:
            self.document_info.setText("Файл не выбран")
            self.document_info.setStyleSheet("color: #718096; font-size: 9pt;")
            self.document_info.setToolTip("")
            return

        path = Path(raw).expanduser()
        if not path.is_file():
            self.document_info.setText("Файл не найден — проверьте путь")
            self.document_info.setStyleSheet(
                "color: #dc2626; font-size: 9pt; font-weight: 600;"
            )
            self.document_info.setToolTip(str(path))
            return

        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size < 1024:
            size_text = f"{size} Б"
        elif size < 1024 * 1024:
            size_text = f"{size / 1024:.0f} КБ"
        else:
            size_text = f"{size / (1024 * 1024):.1f} МБ"

        extension = path.suffix.lower().lstrip(".").upper() or "ФАЙЛ"
        self.document_info.setText(f"{path.name}  ·  {extension}  ·  {size_text}")
        self.document_info.setStyleSheet("color: #64748b; font-size: 9pt;")
        self.document_info.setToolTip(str(path))

    def _refresh_printer_hint(self) -> None:
        available = available_printers()
        selected = str(self.printer_combo.currentData() or "")
        if not available:
            self.printer_hint.setText(
                "Принтеры не найдены. Подключите принтер и нажмите «Обновить список»."
            )
            self.printer_hint.setStyleSheet(
                "color: #dc2626; font-size: 9pt; font-weight: 600;"
            )
            return
        if selected and selected not in available:
            self.printer_hint.setText(
                "Сохранённый принтер недоступен. Выберите другой из списка."
            )
            self.printer_hint.setStyleSheet(
                "color: #d97706; font-size: 9pt; font-weight: 600;"
            )
            return
        self.printer_hint.setText(
            "PDF, изображения и текст печатаются напрямую. Файлы Office "
            "отправляются через связанное приложение Windows."
        )
        self.printer_hint.setStyleSheet("color: #718096; font-size: 9pt;")

    def _set_weekdays(self, weekdays: range) -> None:
        selected = set(weekdays)
        for index, button in enumerate(self.day_buttons):
            button.blockSignals(True)
            button.setChecked(index in selected)
            button.blockSignals(False)
        self._on_settings_changed()

    def _clear_log(self) -> None:
        self.log_view.clear()
        self._append_log("Журнал очищен.")

    def _open_settings_folder(self) -> None:
        directory = app_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def _open_log_file(self) -> None:
        path = log_file()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "Журнал",
                f"Файл журнала ещё не создан:\n{path}",
            )

    def _append_log(self, message: str) -> None:
        if not hasattr(self, "log_view"):
            return
        stamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.log_view.appendPlainText(f"{stamp}  {message}")
        LOGGER.info(message)

    def _notify(
        self,
        title: str,
        message: str,
        warning: bool = False,
    ) -> None:
        if self._tray is None:
            return
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if warning
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray.showMessage(title, message, icon, 6000)

    # ------------------------------------------------------------------
    # Состояние и расписание
    # ------------------------------------------------------------------
    def _setup_scheduler(self) -> None:
        self._scheduler = Scheduler(self.settings, self)
        self._scheduler.due.connect(self._on_schedule_due)
        self._scheduler.checked.connect(self._update_next_run_label)
        if self.settings.enabled:
            self._scheduler.start()

    def _update_header_status(self) -> None:
        if not hasattr(self, "status_pill"):
            return
        current = self._ui_settings() if not self._loading else self.settings
        if not current.enabled:
            self._set_status_pill("Расписание выключено", "#eef2f7", "#64748b", "")
            return

        problem = self._schedule_problem(current)
        if problem:
            self._set_status_pill("Нужна настройка", "#fff4e5", "#b45309", problem)
        else:
            self._set_status_pill("Расписание активно", "#e8f7ef", "#15803d", "")

    def _set_status_pill(
        self,
        text: str,
        background: str,
        color: str,
        tooltip: str,
    ) -> None:
        self.status_pill.setText(text)
        self.status_pill.setToolTip(tooltip)
        self.status_pill.setStyleSheet(
            "QLabel {"
            f"background: {background}; color: {color};"
            "border-radius: 11px; padding: 5px 12px;"
            "font-weight: 600; font-size: 9pt;"
            "}"
        )

    def _schedule_problem(self, settings: Settings) -> str | None:
        if not settings.enabled:
            return None
        if not settings.normalized_weekdays():
            return "Выберите хотя бы один день недели."
        return validate_print_setup(settings)

    def _refresh_time_labels(self) -> None:
        self._update_next_run_label()
        self._update_header_status()
        self._sync_tray()

    def _update_next_run_label(self) -> None:
        if not hasattr(self, "next_run_label"):
            return
        current = self._ui_settings() if not self._loading else self.settings
        if not current.enabled:
            self.next_run_label.setText("Расписание выключено.")
            self.next_run_label.setStyleSheet(
                "color: #64748b; font-weight: 600; font-size: 9.5pt;"
            )
            return

        if not current.normalized_weekdays():
            self.next_run_label.setText(
                "Выберите дни недели, в которые нужна автоматическая печать."
            )
            self.next_run_label.setStyleSheet(
                "color: #b45309; font-weight: 600; font-size: 9.5pt;"
            )
            return

        now = datetime.now()
        occurrence = next_occurrence(current, now)
        if occurrence is None:
            self.next_run_label.setText("Ближайший запуск не рассчитан.")
            return

        if occurrence <= now:
            self.next_run_label.setText(
                f"Время наступило ({occurrence:%H:%M}) — печать ожидает выполнения."
            )
            self.next_run_label.setStyleSheet(
                "color: #15803d; font-weight: 600; font-size: 9.5pt;"
            )
            return

        self.next_run_label.setText(
            "Следующий запуск: " + format_human_datetime(occurrence)
        )
        self.next_run_label.setStyleSheet(
            "color: #334155; font-weight: 600; font-size: 9.5pt;"
        )

    def _on_schedule_due(self) -> None:
        if self._quitting or self._quit_requested:
            return
        if self._worker is not None and self._worker.isRunning():
            if not self._pending_schedule:
                self._append_log(
                    "Время печати наступило, но предыдущее задание ещё "
                    "выполняется. Ожидаю завершения."
                )
            self._pending_schedule = True
            return

        self._pending_schedule = False
        current = self._ui_settings()
        if not is_due(current, datetime.now()):
            return

        today = datetime.now().date().isoformat()
        if current.last_triggered_date == today:
            return

        self.settings.last_triggered_date = today
        self._persist()
        self._append_log(
            f"Сработало расписание: {format_human_datetime(datetime.now())}."
        )
        self._start_print("schedule")

    def _start_print(self, trigger: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            if trigger == "manual":
                message = (
                    "Предыдущее задание ещё выполняется. Подождите немного."
                )
                if self.isVisible():
                    QMessageBox.information(self, "Печать", message)
                else:
                    self._notify("Печать", message)
            else:
                self._pending_schedule = True
            return

        if trigger == "manual":
            if not self._persist():
                return
        else:
            # Перед плановой печатью настройки уже сохранены.
            self.settings = self._ui_settings()

        problem = validate_print_setup(self.settings)
        if problem:
            self._append_log(f"Печать не запущена: {problem}")
            self.statusBar().showMessage(problem, 8000)
            if trigger == "manual":
                if self.isVisible():
                    QMessageBox.warning(self, "Печать невозможна", problem)
                else:
                    self._notify("Печать невозможна", problem, warning=True)
            else:
                self._notify("Печать не выполнена", problem, warning=True)
            return

        self._pending_schedule = False
        self.print_button.setEnabled(False)
        self.print_button.setText("Отправка…")
        kind = "Плановая" if trigger == "schedule" else "Ручная"
        self._append_log(
            f"{kind} печать: «{Path(self.settings.document_path).name}» → "
            f"«{self.settings.printer_name}»."
        )
        self.statusBar().showMessage("Отправка документа на печать…")

        worker = PrintTask(
            self.settings.document_path,
            self.settings.printer_name,
            self,
        )
        self._worker = worker
        worker.succeeded.connect(
            lambda message, source=trigger: self._print_succeeded(message, source)
        )
        worker.failed.connect(
            lambda error, source=trigger: self._print_failed(error, source)
        )
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _print_succeeded(self, message: str, trigger: str) -> None:
        self._append_log(message)
        self.statusBar().showMessage("Задание печати отправлено", 6000)
        if trigger == "schedule" or self.isHidden() or self.isMinimized():
            self._notify("Задание печати", message)

    def _print_failed(self, error: str, trigger: str) -> None:
        self._append_log(f"Ошибка печати: {error}")
        self.statusBar().showMessage("Ошибка печати", 8000)
        if trigger == "manual" and self.isVisible():
            QMessageBox.critical(self, "Ошибка печати", error)
        else:
            self._notify("Ошибка печати", error, warning=True)

    def _worker_finished(self) -> None:
        self._worker = None
        self.print_button.setEnabled(True)
        self.print_button.setText("Печать сейчас")
        self._refresh_time_labels()
        if self._quit_requested:
            self._finalize_quit()
            return
        if not self._quitting:
            QTimer.singleShot(700, self._scheduler.check_now)

    def _print_now(self) -> None:
        self._start_print("manual")

    # ------------------------------------------------------------------
    # Трей и завершение работы
    # ------------------------------------------------------------------
    def _setup_tray(self) -> None:
        self._tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_check.blockSignals(True)
            self.tray_check.setChecked(False)
            self.tray_check.blockSignals(False)
            self.tray_check.setEnabled(False)
            self.tray_check.setToolTip(
                "Системный трей недоступен в текущей сессии Windows."
            )
            return

        tray = QSystemTrayIcon(self._app_icon, self)
        menu = QMenu(self)

        open_action = QAction("Открыть окно", self)
        open_action.triggered.connect(self.show_window)
        menu.addAction(open_action)
        menu.addSeparator()

        self.print_action = QAction("Печать сейчас", self)
        self.print_action.triggered.connect(self._print_now)
        menu.addAction(self.print_action)

        self.tray_schedule_action = QAction("Расписание включено", self)
        self.tray_schedule_action.setCheckable(True)
        self.tray_schedule_action.toggled.connect(self._on_tray_schedule_toggled)
        menu.addAction(self.tray_schedule_action)
        menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self._quit)
        menu.addAction(exit_action)

        tray.setContextMenu(menu)
        tray.setToolTip(APP_DISPLAY_NAME)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _sync_tray(self) -> None:
        tray = getattr(self, "_tray", None)
        if tray is None:
            return
        current = self._ui_settings() if not self._loading else self.settings
        self.tray_schedule_action.blockSignals(True)
        self.tray_schedule_action.setChecked(current.enabled)
        self.tray_schedule_action.blockSignals(False)

        if not current.enabled:
            tray.setToolTip(f"{APP_DISPLAY_NAME} — расписание выключено")
            return
        occurrence = next_occurrence(current, datetime.now())
        if occurrence:
            tray.setToolTip(
                f"{APP_DISPLAY_NAME}\nСледующий запуск: {occurrence:%d.%m.%Y %H:%M}"
            )
        else:
            tray.setToolTip(f"{APP_DISPLAY_NAME} — расписание включено")

    def _on_tray_schedule_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self.schedule_check.setChecked(checked)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def _apply_startup_visibility(self) -> None:
        if self._start_minimized:
            if self._tray is not None:
                self.hide()
                self._notify(
                    APP_DISPLAY_NAME,
                    "Приложение работает в фоне и продолжит печать по расписанию.",
                )
            else:
                self.show()
        else:
            self.show()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _save_before_quit(self) -> None:
        self._save_timer.stop()
        self._persist()

    def _quit(self) -> None:
        if self._quitting:
            return
        self._save_before_quit()
        self._quit_requested = True
        if self._worker is not None and self._worker.isRunning():
            self._append_log("Ожидание завершения текущего задания перед выходом…")
            self.hide()
            return
        self._finalize_quit()

    def _finalize_quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self._save_timer.stop()
        self._scheduler.stop()
        if self._tray is not None:
            self._tray.hide()
        LOGGER.info("Приложение завершено")
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quit_requested or self._quitting:
            event.accept()
            return
        if self._tray is not None and self.tray_check.isChecked():
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self._notify(
                    APP_DISPLAY_NAME,
                    "Окно свёрнуто в трей. Приложение продолжает работать.",
                )
            return
        event.accept()
        self._quit()

    # ------------------------------------------------------------------
    # Один экземпляр приложения и drag&drop
    # ------------------------------------------------------------------
    def _accept_instance_connection(self) -> None:
        server = self._local_server
        if server is None:
            return
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            connection.setParent(self)
            connection.readyRead.connect(
                lambda socket=connection: self._read_instance_socket(socket)
            )
            connection.disconnected.connect(connection.deleteLater)
            if connection.bytesAvailable() > 0:
                self._read_instance_socket(connection)

    def _read_instance_socket(self, connection: QLocalSocket) -> None:
        data = bytes(connection.readAll())
        if b"show" in data:
            self.show_window()
        connection.disconnectFromServer()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if url.isLocalFile() and path.is_file():
                self.document_edit.setText(str(path))
                self._append_log(f"Документ перетащен в окно: {path}")
                event.acceptProposedAction()
                return
        event.ignore()
