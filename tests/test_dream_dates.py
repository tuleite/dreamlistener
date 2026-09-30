from datetime import datetime, timezone
import unittest

from app.dream_dates import (
    extract_narrated_dream_date,
    received_date_in_application_timezone,
)


class DreamDatesTest(unittest.TestCase):
    def setUp(self) -> None:
        # 02:30 UTC do dia 30 ainda é 23:30 do dia 29 em São Paulo.
        self.received_at = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)

    def test_received_date_uses_the_diary_timezone(self) -> None:
        self.assertEqual(
            str(received_date_in_application_timezone(self.received_at)), "2026-09-29"
        )

    def test_extracts_an_explicit_complete_date(self) -> None:
        candidate = extract_narrated_dream_date(
            "O sonho aconteceu em 12/09/2026.", self.received_at
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(str(candidate.value), "2026-09-12")
        self.assertEqual(candidate.source, "narrated_explicit_date")

    def test_extracts_relative_date_using_the_diary_timezone(self) -> None:
        candidate = extract_narrated_dream_date("Eu tive esse sonho ontem.", self.received_at)

        self.assertIsNotNone(candidate)
        self.assertEqual(str(candidate.value), "2026-09-28")
        self.assertEqual(candidate.source, "narrated_relative_date")

    def test_ignores_ambiguous_and_invalid_dates(self) -> None:
        self.assertIsNone(extract_narrated_dream_date("Foi em 12/09.", self.received_at))
        self.assertIsNone(extract_narrated_dream_date("Foi em 31/02/2026.", self.received_at))


if __name__ == "__main__":
    unittest.main()
