from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal

from .config import Settings

# Небольшой запас нужен, если компьютер вышел из сна или приложение
# запустилось вскоре после назначенного времени.
GRACE_PERIOD_SECONDS = 5 * 60


def is_due(
    settings: Settings,
    now: datetime,
    grace_period: int = GRACE_PERIOD_SECONDS,
) -> bool:
    if not settings.enabled or not settings.normalized_weekdays():
        return False
    if now.weekday() not in settings.normalized_weekdays():
        return False
    if settings.last_triggered_date == now.date().isoformat():
        return False

    target = datetime.combine(now.date(), settings.scheduled_time())
    elapsed = (now - target).total_seconds()
    return 0 <= elapsed <= grace_period


def next_occurrence(
    settings: Settings,
    now: datetime | None = None,
) -> datetime | None:
    """Ближайшее время запуска или None, если расписание выключено."""
    if not settings.enabled or not settings.normalized_weekdays():
        return None

    current = now or datetime.now()
    weekdays = settings.normalized_weekdays()
    target_time = settings.scheduled_time()

    for offset in range(8):
        target_date = current.date() + timedelta(days=offset)
        if target_date.weekday() not in weekdays:
            continue

        target = datetime.combine(target_date, target_time)
        if target > current:
            return target

        # Время уже наступило сегодня, но печать ещё возможна в пределах
        # периода ожидания (например, после запуска приложения).
        if (
            offset == 0
            and settings.last_triggered_date != target_date.isoformat()
            and 0 <= (current - target).total_seconds() <= GRACE_PERIOD_SECONDS
        ):
            return target

    return None


class Scheduler(QObject):
    due = pyqtSignal()
    checked = pyqtSignal()

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._timer = QTimer(self)
        self._timer.setInterval(10_000)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._check)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        if settings.enabled:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        QTimer.singleShot(800, self._check)

    def stop(self) -> None:
        self._timer.stop()

    def check_now(self) -> None:
        self._check()

    def _check(self) -> None:
        if is_due(self.settings, datetime.now()):
            self.due.emit()
        self.checked.emit()
