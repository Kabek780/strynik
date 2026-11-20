from __future__ import annotations

import argparse
import ctypes
import logging
import sys

from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox

from printer_scheduler.config import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION,
    SINGLE_INSTANCE_NAME,
    setup_logging,
    synchronize_autostart_command,
)
from printer_scheduler.gui import STYLE_SHEET, MainWindow, make_app_icon

LOGGER = logging.getLogger(__name__)


def _notify_existing_instance() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_NAME)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


def _install_exception_hook() -> None:
    def handle_exception(exc_type, exc_value, traceback) -> None:
        LOGGER.critical(
            "Необработанное исключение",
            exc_info=(exc_type, exc_value, traceback),
        )
        sys.__excepthook__(exc_type, exc_value, traceback)

    sys.excepthook = handle_exception


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Автоматическая печать документа по расписанию."
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="запустить свёрнутым в системный трей",
    )
    args, _ = parser.parse_known_args()
    return args


def main() -> int:
    args = _parse_args()
    setup_logging()
    _install_exception_hook()

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PrintScheduler.App.1"
            )
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE_SHEET)
    app.setWindowIcon(make_app_icon())
    QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))

    server = QLocalServer()
    if _notify_existing_instance():
        LOGGER.info("Найден уже запущенный экземпляр приложения.")
        return 0

    # Сокет мог остаться после аварийного завершения.
    QLocalServer.removeServer(SINGLE_INSTANCE_NAME)
    if not server.listen(SINGLE_INSTANCE_NAME):
        QMessageBox.critical(
            None,
            APP_DISPLAY_NAME,
            "Не удалось запустить приложение: "
            f"системный сокет занят.\n{server.errorString()}",
        )
        return 1

    try:
        synchronize_autostart_command()
    except (OSError, RuntimeError) as exc:
        LOGGER.warning("Не удалось обновить автозагрузку: %s", exc)

    _window = MainWindow(
        start_minimized=args.minimized,
        local_server=server,
    )

    exit_code = app.exec()
    server.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
