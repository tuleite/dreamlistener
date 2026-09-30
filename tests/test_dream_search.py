from datetime import date
import unittest

from app.dream_search import parse_search_criteria, render_result_count, split_for_telegram


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

    def test_result_count_explains_when_only_the_first_results_are_shown(self) -> None:
        self.assertEqual(
            render_result_count(22, 5),
            "🔎 Encontrados 22 resultados. Exibindo os 5 primeiros:",
        )

    def test_result_count_handles_empty_search(self) -> None:
        self.assertEqual(
            render_result_count(0, 0),
            "🔎 Nenhum sonho publicado corresponde à busca.",
        )

    def test_long_results_are_split_without_losing_any_content(self) -> None:
        text = "primeiro\n\nsegundo\n\nterceiro"

        chunks = split_for_telegram(text, maximum_length=10)

        self.assertEqual(chunks, ["primeiro", "segundo", "terceiro"])
        self.assertEqual("\n\n".join(chunks), text)

    def test_a_single_long_section_is_split_at_the_message_limit(self) -> None:
        chunks = split_for_telegram("abcdefgh", maximum_length=3)

        self.assertEqual(chunks, ["abc", "def", "gh"])
