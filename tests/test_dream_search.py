from datetime import date
import unittest

from app.dream_search import parse_search_criteria


class DreamSearchTest(unittest.TestCase):
    def test_parses_text_dates_and_tag_together(self) -> None:
        criteria = parse_search_criteria([
            "rio", "tag:agua", "de:2026-09-01", "ate:2026-09-30"
        ])

        self.assertEqual(criteria.text, "rio")
        self.assertEqual(criteria.tag, "agua")
        self.assertEqual(criteria.start_date, date(2026, 9, 1))
        self.assertEqual(criteria.end_date, date(2026, 9, 30))

    def test_keeps_quoted_words_as_one_text_query(self) -> None:
        criteria = parse_search_criteria(['"casa antiga"', "tag:casa"])

        self.assertEqual(criteria.text, "casa antiga")
        self.assertEqual(criteria.tag, "casa")

    def test_rejects_an_inverted_date_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "não pode ser posterior"):
            parse_search_criteria(["de:2026-10-01", "ate:2026-09-01"])

    def test_rejects_ambiguous_date_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "AAAA-MM-DD"):
            parse_search_criteria(["de:30/09/2026"])
