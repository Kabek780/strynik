from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QImage
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication

from printer_scheduler.config import Settings
from printer_scheduler.printing import (
    PrintError,
    _read_text,
    print_document,
    print_to_device,
    validate_print_setup,
)


def _pdf_printer(path: Path) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    return printer


class PrintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary.name)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _assert_printed(self, source: Path) -> None:
        output = self.directory / f"{source.name}.out.pdf"
        message = print_to_device(source, _pdf_printer(output))
        self.assertTrue(output.is_file())
        self.assertGreater(output.stat().st_size, 0)
        self.assertIn(source.name, message)

    def test_read_text_encodings(self) -> None:
        cases = {
            "utf8.txt": ("Привет, мир", "utf-8"),
            "utf8bom.txt": ("Привет, мир", "utf-8-sig"),
            "cp1251.txt": ("Привет, мир", "cp1251"),
            "utf16.txt": ("Привет, мир", "utf-16"),
        }
        for name, (text, encoding) in cases.items():
            path = self.directory / name
            path.write_bytes(text.encode(encoding))
            self.assertEqual(_read_text(path), text, name)

    def test_print_text_documents(self) -> None:
        documents = {
            "plain.txt": "Простой текст",
            "notes.md": "# Заголовок\n\nТекст **Markdown**",
            "page.html": "<h1>Заголовок</h1><p>Текст HTML</p>",
        }
        for name, content in documents.items():
            path = self.directory / name
            path.write_text(content, encoding="utf-8")
            self._assert_printed(path)

    def test_print_image(self) -> None:
        path = self.directory / "image.png"
        image = QImage(120, 80, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        self.assertTrue(image.save(str(path)))
        self._assert_printed(path)

    def test_print_pdf(self) -> None:
        try:
            import pymupdf
        except ImportError:
            self.skipTest("PyMuPDF не установлен")

        source = self.directory / "document.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "PDF document")
        document.save(str(source))
        document.close()
        self._assert_printed(source)

    def test_validate_print_setup(self) -> None:
        self.assertIn("Не выбран документ", validate_print_setup(Settings()))

        missing = self.directory / "missing.pdf"
        self.assertIn(
            "Файл не найден",
            validate_print_setup(Settings(document_path=str(missing))),
        )

        existing = self.directory / "document.txt"
        existing.write_text("text", encoding="utf-8")
        self.assertIn(
            "Не выбран принтер",
            validate_print_setup(Settings(document_path=str(existing))),
        )
        self.assertIn(
            "недоступен",
            validate_print_setup(
                Settings(
                    document_path=str(existing),
                    printer_name="Printer That Does Not Exist 12345",
                )
            ),
        )

    def test_print_document_rejects_missing_file(self) -> None:
        with self.assertRaises(PrintError):
            print_document(self.directory / "missing.txt", "Any Printer")


if __name__ == "__main__":
    unittest.main()
