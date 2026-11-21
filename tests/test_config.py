from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from printer_scheduler.config import (
    Settings,
    autostart_command,
    load_settings,
    save_settings,
    settings_file,
)


class SettingsTests(unittest.TestCase):
    def test_unknown_fields_are_ignored_and_values_normalized(self) -> None:
        settings = Settings.from_dict(
            {
                "document_path": "  C:\\test.pdf  ",
                "printer_name": " Printer ",
                "weekdays": [4, 0, 0, 8, "2", "bad"],
                "print_time": "25:99",
                "enabled": 1,
                "unknown": "ignored",
            }
        )
        self.assertEqual(settings.document_path, "C:\\test.pdf")
        self.assertEqual(settings.printer_name, "Printer")
        self.assertEqual(settings.weekdays, [0, 2, 4])
        self.assertEqual(settings.print_time, "09:00")
        self.assertTrue(settings.enabled)

    def test_invalid_last_triggered_date_is_cleared(self) -> None:
        settings = Settings.from_dict({"last_triggered_date": "not-a-date"})
        self.assertEqual(settings.last_triggered_date, "")

    def test_malformed_weekdays_are_ignored(self) -> None:
        for value in (5, None, {"monday": True}):
            with self.subTest(value=value):
                settings = Settings.from_dict({"weekdays": value})
                self.assertEqual(settings.weekdays, [])

    def test_save_and_load_round_trip(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"APPDATA": directory}),
        ):
            expected = Settings(
                document_path="C:\\Документы\\отчёт.pdf",
                printer_name="HP LaserJet",
                weekdays=[0, 2, 4],
                print_time="14:35",
                enabled=True,
                autostart=False,
                minimize_to_tray=True,
            )
            save_settings(expected)
            self.assertTrue(settings_file().is_file())
            actual = load_settings()
            self.assertEqual(actual, expected)

    def test_missing_file_returns_defaults(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"APPDATA": directory}),
        ):
            self.assertEqual(load_settings(), Settings())

    def test_autostart_command_has_script_and_key(self) -> None:
        command = autostart_command()
        self.assertIn("main.py", command)
        self.assertIn("--minimized", command)
        self.assertIn("python", command.lower())


if __name__ == "__main__":
    unittest.main()
