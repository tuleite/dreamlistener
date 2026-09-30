import unittest

from app.access_control import is_allowed_chat, parse_allowed_chat_ids


class AccessControlTest(unittest.TestCase):
    def test_parses_multiple_chat_ids(self) -> None:
        self.assertEqual(parse_allowed_chat_ids("42, -100123, 7"), frozenset({42, -100123, 7}))

    def test_empty_allowlist_denies_access(self) -> None:
        allowed = parse_allowed_chat_ids(None)
        self.assertFalse(is_allowed_chat(42, allowed))

    def test_rejects_invalid_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "apenas números"):
            parse_allowed_chat_ids("42, nao-e-um-id")
