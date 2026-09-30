import unittest

from app.dream_tags import extract_factual_tags


class DreamTagsTest(unittest.TestCase):
    def test_extracts_only_explicit_mentions(self) -> None:
        tags = extract_factual_tags("Eu estava em casa com minha mãe, perto de um rio.")

        self.assertEqual(tags, ["agua", "casa", "familia"])

    def test_normalizes_accents_and_does_not_infer_meaning(self) -> None:
        tags = extract_factual_tags("Peguei um ônibus para a escola.")

        self.assertEqual(tags, ["escola", "transporte"])
        self.assertNotIn("seguranca", tags)
        self.assertNotIn("arquetipo", tags)

    def test_does_not_match_keywords_inside_larger_words(self) -> None:
        self.assertEqual(extract_factual_tags("A casinha era azul."), [])
