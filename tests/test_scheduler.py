from __future__ import annotations

import unittest
from datetime import datetime

from printer_scheduler.config import Settings
from printer_scheduler.scheduler import is_due, next_occurrence


class SchedulerTests(unittest.TestCase):
    def test_due_at_scheduled_time(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
        )
        self.assertTrue(is_due(settings, datetime(2026, 11, 20, 9, 0, 30)))

    def test_due_only_on_selected_weekday(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[0],
            print_time="09:00",
        )
        self.assertFalse(is_due(settings, datetime(2026, 11, 20, 9, 0, 30)))

    def test_due_within_grace_period(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
        )
        self.assertTrue(is_due(settings, datetime(2026, 11, 20, 9, 4, 59)))
        self.assertFalse(is_due(settings, datetime(2026, 11, 20, 9, 5, 1)))

    def test_due_does_not_repeat_on_same_day(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
            last_triggered_date="2026-11-20",
        )
        self.assertFalse(is_due(settings, datetime(2026, 11, 20, 9, 0, 30)))

    def test_disabled_schedule_is_never_due(self) -> None:
        settings = Settings(
            enabled=False,
            weekdays=[4],
            print_time="09:00",
        )
        self.assertFalse(is_due(settings, datetime(2026, 11, 20, 9, 0, 30)))
        self.assertIsNone(next_occurrence(settings, datetime(2026, 11, 20, 8, 0)))

    def test_next_occurrence_today(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
        )
        self.assertEqual(
            next_occurrence(settings, datetime(2026, 11, 20, 8, 0)),
            datetime(2026, 11, 20, 9, 0),
        )

    def test_next_occurrence_skips_triggered_today(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
            last_triggered_date="2026-11-20",
        )
        self.assertEqual(
            next_occurrence(settings, datetime(2026, 11, 20, 9, 1)),
            datetime(2026, 11, 27, 9, 0),
        )

    def test_next_occurrence_across_week(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[0, 2, 4],
            print_time="09:00",
            last_triggered_date="2026-11-20",
        )
        self.assertEqual(
            next_occurrence(settings, datetime(2026, 11, 20, 9, 1)),
            datetime(2026, 11, 23, 9, 0),
        )

    def test_next_occurrence_during_grace_period(self) -> None:
        settings = Settings(
            enabled=True,
            weekdays=[4],
            print_time="09:00",
        )
        self.assertEqual(
            next_occurrence(settings, datetime(2026, 11, 20, 9, 2)),
            datetime(2026, 11, 20, 9, 0),
        )


if __name__ == "__main__":
    unittest.main()
