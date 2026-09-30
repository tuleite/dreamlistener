import unittest

from app.dream_index import render_published_dream_index
from app.dream_store import Dream


class DreamIndexTest(unittest.TestCase):
    def test_index_contains_only_persisted_facts(self) -> None:
        dream = Dream(
            id="abc123",
            source="telegram",
            source_chat_id=42,
            source_message_id=7,
            received_at="2026-09-30T12:00:00+00:00",
            dream_date="2026-09-29",
            dream_date_source="received_at",
            status="published",
            raw_transcript="texto que não deve aparecer no índice",
            refined_transcript="texto refinado que também não deve aparecer",
            document_url="https://docs.google.com/document/d/example/edit",
            error_message=None,
            created_at="2026-09-30T12:00:00+00:00",
            updated_at="2026-09-30T12:00:00+00:00",
        )

        index = render_published_dream_index([dream])

        self.assertIn("29/09/2026", index)
        self.assertIn("dreamlistener:abc123", index)
        self.assertIn(dream.document_url, index)
        self.assertNotIn(dream.raw_transcript, index)
        self.assertNotIn(dream.refined_transcript, index)

    def test_empty_index_has_an_explicit_message(self) -> None:
        self.assertIn("Nenhum sonho publicado", render_published_dream_index([]))
