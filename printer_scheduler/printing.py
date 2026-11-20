from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path

from PyQt6.QtCore import QRectF, QSizeF, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QFont,
    QImage,
    QImageReader,
    QPageLayout,
    QPainter,
    QTextDocument,
)
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo

from .config import Settings

LOGGER = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".log", ".csv", ".ini", ".cfg", ".conf"}
HTML_EXTENSIONS = {".html", ".htm"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


class PrintError(RuntimeError):
    pass


def available_printers() -> list[str]:
    return [printer.printerName() for printer in QPrinterInfo.availablePrinters()]


def default_printer_name() -> str:
    printer = QPrinterInfo.defaultPrinter()
    return printer.printerName() if not printer.isNull() else ""


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _load_image(path: Path) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        reason = reader.errorString() or "неизвестный формат"
        raise PrintError(f"Не удалось открыть изображение: {reason}")
    return image


def _set_orientation_for_size(printer: QPrinter, size: QSizeF) -> None:
    if size.isEmpty():
        return
    orientation = (
        QPageLayout.Orientation.Landscape
        if size.width() > size.height()
        else QPageLayout.Orientation.Portrait
    )
    printer.setPageOrientation(orientation)


def _paint_image(printer: QPrinter, painter: QPainter, image: QImage) -> None:
    page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
    if page_rect.isEmpty():
        page_rect = QRectF(0, 0, printer.width(), printer.height())
    if page_rect.isEmpty():
        raise PrintError("Принтер сообщил пустую область печати.")

    available = page_rect.size().toSize()
    scaled = image.size().scaled(
        available,
        Qt.AspectRatioMode.KeepAspectRatio,
    )
    target = QRectF(
        page_rect.x() + (page_rect.width() - scaled.width()) / 2,
        page_rect.y() + (page_rect.height() - scaled.height()) / 2,
        scaled.width(),
        scaled.height(),
    )
    painter.drawImage(target, image)


def _print_pdf_with_fitz(path: Path, printer: QPrinter) -> bool:
    """Печатает PDF через PyMuPDF. False означает, что модуль не установлен."""
    try:
        try:
            import pymupdf as fitz  # PyMuPDF
        except ImportError:
            import fitz  # PyMuPDF < 1.24
    except Exception as exc:
        LOGGER.warning(
            "PyMuPDF недоступен (%s). PDF будет открыт приложением Windows.",
            exc,
        )
        return False

    try:
        document = fitz.open(str(path))
    except Exception as exc:
        raise PrintError(f"Не удалось открыть PDF: {exc}") from exc

    try:
        if document.needs_pass:
            raise PrintError("PDF защищён паролем и не может быть напечатан.")
        if document.page_count == 0:
            raise PrintError("PDF не содержит страниц.")

        first_page = document.load_page(0)
        _set_orientation_for_size(
            printer, QSizeF(first_page.rect.width, first_page.rect.height)
        )

        painter = QPainter()
        if not painter.begin(printer):
            raise PrintError("Не удалось запустить печать PDF на выбранном принтере.")
        try:
            matrix = fitz.Matrix(200 / 72, 200 / 72)
            for index in range(document.page_count):
                page = document.load_page(index)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                image = QImage(
                    pixmap.samples,
                    pixmap.width,
                    pixmap.height,
                    pixmap.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
                if image.isNull():
                    raise PrintError(
                        f"Не удалось подготовить страницу PDF {index + 1}."
                    )
                if index > 0:
                    printer.newPage()
                _paint_image(printer, painter, image)
        finally:
            painter.end()
    finally:
        document.close()

    return True


def _print_image(path: Path, printer: QPrinter) -> None:
    image = _load_image(path)
    _set_orientation_for_size(printer, QSizeF(image.size()))

    painter = QPainter()
    if not painter.begin(printer):
        raise PrintError("Не удалось запустить печать изображения.")
    try:
        _paint_image(printer, painter, image)
    finally:
        painter.end()


def _print_text_document(path: Path, printer: QPrinter, extension: str) -> None:
    text = _read_text(path)
    document = QTextDocument()
    document.setDefaultFont(QFont("Segoe UI", 10))
    document.setDocumentMargin(42)

    if extension in HTML_EXTENSIONS:
        document.setBaseUrl(QUrl.fromLocalFile(str(path.parent) + os.sep))
        document.setHtml(text)
    elif extension in MARKDOWN_EXTENSIONS:
        document.setBaseUrl(QUrl.fromLocalFile(str(path.parent) + os.sep))
        document.setMarkdown(text)
    else:
        document.setPlainText(text)

    document.print(printer)


def _print_via_windows_shell(path: Path, printer_name: str) -> str:
    if os.name != "nt":
        raise PrintError(
            "Для этого типа файла нужна Windows и связанное приложение для печати."
        )

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_int,
    ]
    shell32.ShellExecuteW.restype = ctypes.c_void_p

    result = shell32.ShellExecuteW(
        None,
        "printto",
        str(path),
        f'"{printer_name}"',
        str(path.parent),
        0,  # SW_HIDE
    )
    if not result or int(result) <= 32:
        code = ctypes.get_last_error()
        raise PrintError(
            "Windows не смогла отправить файл на печать. "
            "Проверьте, что для этого типа файла установлено приложение "
            f"и принтер доступен (код {code or int(result or 0)})."
        )

    LOGGER.info("Файл передан приложению Windows через PrintTo.")
    return (
        f"Файл «{path.name}» передан приложению Windows для печати "
        f"на «{printer_name}». Завершение задания контролирует это приложение."
    )


def print_to_device(path: str | Path, printer: QPrinter) -> str:
    """Подготавливает документ и отправляет его на QPrinter."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise PrintError(f"Файл не найден: {file_path}")

    extension = file_path.suffix.lower()
    printer.setDocName(file_path.name)

    if extension == ".pdf":
        if not _print_pdf_with_fitz(file_path, printer):
            return _print_via_windows_shell(file_path, printer.printerName())
    elif extension in IMAGE_EXTENSIONS:
        _print_image(file_path, printer)
    elif extension in TEXT_EXTENSIONS | HTML_EXTENSIONS | MARKDOWN_EXTENSIONS:
        _print_text_document(file_path, printer, extension)
    else:
        return _print_via_windows_shell(file_path, printer.printerName())

    return (
        f"Документ «{file_path.name}» отправлен на принтер «{printer.printerName()}»."
    )


def print_document(path: str | Path, printer_name: str) -> str:
    """Печатает документ на выбранном установленном принтере."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise PrintError(f"Файл не найден: {file_path}")
    if not printer_name:
        raise PrintError("Принтер не выбран.")
    if printer_name not in available_printers():
        raise PrintError(f"Принтер «{printer_name}» недоступен.")

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
    printer.setPrinterName(printer_name)
    printer.setDocName(file_path.name)
    if not printer.isValid():
        raise PrintError(
            f"Не удалось подключиться к принтеру «{printer_name}». "
            "Проверьте, что он включён."
        )

    LOGGER.info("Печать «%s» на «%s»", file_path, printer_name)
    result = print_to_device(file_path, printer)
    LOGGER.info("Задание печати отправлено: %s", result)
    return result


class PrintTask(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        document_path: str,
        printer_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.document_path = document_path
        self.printer_name = printer_name

    def run(self) -> None:
        try:
            message = print_document(self.document_path, self.printer_name)
        except Exception as exc:
            LOGGER.exception("Ошибка печати")
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.succeeded.emit(message)


def validate_print_setup(settings: Settings) -> str | None:
    """Возвращает описание первой проблемы или None, если можно печатать."""
    if not settings.document_path:
        return "Не выбран документ для печати."
    path = Path(settings.document_path).expanduser()
    if not path.is_file():
        return f"Файл не найден: {path}"
    if not settings.printer_name:
        return "Не выбран принтер."
    if settings.printer_name not in available_printers():
        return f"Принтер «{settings.printer_name}» недоступен."
    return None
