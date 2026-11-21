from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

APP_NAME = "PrintScheduler"
APP_DISPLAY_NAME = "Планировщик печати"
APP_VERSION = "1.0.0"

# Один экземпляр на пользователя: настройки и автозагрузка тоже раздельные.
_USER_KEY = hashlib.sha1(
    (os.environ.get("USERNAME") or str(Path.home())).encode("utf-8")
).hexdigest()[:10]
SINGLE_INSTANCE_NAME = f"PrintScheduler.SingleInstance.v1.{_USER_KEY}"

AUTOSTART_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE_NAME = "PrintScheduler"

RU_WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
RU_WEEKDAYS_FULL = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)
RU_MONTHS_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def app_data_dir() -> Path:
    """Каталог с настройками и журналом приложения."""
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".config"
    return root / APP_NAME


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def log_file() -> Path:
    return app_data_dir() / "app.log"


def setup_logging() -> None:
    """Пишет журнал рядом с настройками и, при запуске из консоли, в stderr."""
    from logging.handlers import RotatingFileHandler

    handlers: list[logging.Handler] = []
    try:
        directory = app_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_file(),
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
    except OSError:
        # Приложение должно запускаться даже при проблемах с папкой APPDATA.
        pass

    if sys.stderr is not None and not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())
    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
        handlers=handlers,
        force=True,
    )


@dataclass
class Settings:
    document_path: str = ""
    printer_name: str = ""
    weekdays: list[int] = field(default_factory=list)
    print_time: str = "09:00"
    enabled: bool = False
    autostart: bool = False
    minimize_to_tray: bool = True
    last_triggered_date: str = ""

    def scheduled_time(self) -> time:
        try:
            return datetime.strptime(self.print_time, "%H:%M").time()
        except (TypeError, ValueError):
            return time(9, 0)

    def normalized_weekdays(self) -> list[int]:
        result: list[int] = []
        try:
            values = list(self.weekdays or [])
        except TypeError:
            # Повреждённые настройки не должны мешать запуску приложения.
            return result
        for value in values:
            try:
                day = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= day <= 6 and day not in result:
                result.append(day)
        return sorted(result)

    def normalize(self) -> None:
        self.document_path = str(self.document_path or "").strip()
        self.printer_name = str(self.printer_name or "").strip()
        self.weekdays = self.normalized_weekdays()
        self.print_time = self.scheduled_time().strftime("%H:%M")
        self.enabled = bool(self.enabled)
        self.autostart = bool(self.autostart)
        self.minimize_to_tray = bool(self.minimize_to_tray)
        self.last_triggered_date = str(self.last_triggered_date or "").strip()

        # Оставляем только корректную дату последнего запуска.
        if self.last_triggered_date:
            try:
                date.fromisoformat(self.last_triggered_date)
            except ValueError:
                self.last_triggered_date = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        defaults = cls()
        known = {field_name for field_name in defaults.__dataclass_fields__}
        values = {key: value for key, value in data.items() if key in known}
        settings = cls(**values)
        settings.normalize()
        return settings


def load_settings() -> Settings:
    path = settings_file()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("корневой элемент настроек должен быть объектом")
        return Settings.from_dict(data)
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning("Не удалось прочитать настройки: %s", exc)
        return Settings()


def save_settings(settings: Settings) -> None:
    settings.normalize()
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def format_human_datetime(value: datetime) -> str:
    return (
        f"{RU_WEEKDAYS_FULL[value.weekday()]}, "
        f"{value.day} {RU_MONTHS_GENITIVE[value.month - 1]} {value.year}, "
        f"{value:%H:%M}"
    )


def _is_windows() -> bool:
    return os.name == "nt"


def autostart_command() -> str:
    """Команда автозапуска для текущего способа запуска приложения."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --minimized'

    python_executable = Path(sys.executable)
    pythonw = python_executable.with_name("pythonw.exe")
    launcher = pythonw if pythonw.is_file() else python_executable
    script = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{launcher}" "{script}" --minimized'


def _read_autostart_value() -> str | None:
    if not _is_windows():
        return None
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE_NAME)
            return str(value)
    except FileNotFoundError:
        return None


def is_autostart_enabled() -> bool:
    if not _is_windows():
        return False
    return _read_autostart_value() is not None


def set_autostart(enabled: bool) -> None:
    if not _is_windows():
        raise RuntimeError("Автозагрузка поддерживается только в Windows.")

    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        AUTOSTART_REGISTRY_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                AUTOSTART_VALUE_NAME,
                0,
                winreg.REG_SZ,
                autostart_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_VALUE_NAME)
            except FileNotFoundError:
                pass


def synchronize_autostart_command() -> None:
    """Обновляет путь в автозагрузке, если приложение было перемещено."""
    if not _is_windows() or not is_autostart_enabled():
        return
    if _read_autostart_value() == autostart_command():
        return
    try:
        set_autostart(True)
        LOGGER.info("Путь приложения в автозагрузке обновлён.")
    except OSError as exc:
        LOGGER.warning("Не удалось обновить автозагрузку: %s", exc)
