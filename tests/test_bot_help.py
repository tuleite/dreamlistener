import unittest

from app.bot_help import COMMANDS, render_help


class BotHelpTest(unittest.TestCase):
    def test_command_catalog_exposes_the_expected_shortcuts(self) -> None:
        self.assertEqual(
            [item.command for item in COMMANDS],
            ["start", "ajuda", "buscar", "retomar_publicacoes"],
        )

    def test_help_explains_search_without_claiming_interpretation(self) -> None:
        help_text = render_help()

        self.assertIn("/buscar tag:casa", help_text)
        self.assertIn("não interpreta sonhos", help_text)
