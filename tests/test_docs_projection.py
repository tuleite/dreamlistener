import unittest

from app.docs_projection import INDEX_PLACEHOLDER, document_contains_marker, dream_marker, index_replacement_request


class DocsProjectionTest(unittest.TestCase):
    def test_marker_is_stable_and_searchable_in_any_tab(self) -> None:
        marker = dream_marker("a2c8")
        document = {
            "tabs": [
                {"documentTab": {"body": {"content": []}}},
                {
                    "documentTab": {
                        "body": {
                            "content": [
                                {
                                    "paragraph": {
                                        "elements": [
                                            {"textRun": {"content": f"🔖 {marker}\n"}}
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                },
            ]
        }

        self.assertEqual(marker, "dreamlistener:a2c8")
        self.assertTrue(document_contains_marker(document, marker))
        self.assertFalse(document_contains_marker(document, dream_marker("other")))

    def test_index_replacement_is_limited_to_the_index_tab(self) -> None:
        replacement = index_replacement_request("index-tab", "• 29/09/2026")["replaceAllText"]
        self.assertEqual(replacement["tabsCriteria"], {"tabIds": ["index-tab"]})
        self.assertEqual(replacement["containsText"]["text"], INDEX_PLACEHOLDER)
        self.assertTrue(replacement["replaceText"].endswith(INDEX_PLACEHOLDER))
