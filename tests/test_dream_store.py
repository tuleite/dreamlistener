from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.dream_store import GOOGLE_PUBLICATION_FAILURE, DreamStore


class DreamStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "dreamlistener.db"
        self.store = DreamStore(database_path)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_same_telegram_message_is_stored_only_once(self) -> None:
        received_at = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        first, created_first = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=99,
            received_at=received_at,
        )
        second, created_second = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=99,
            received_at=received_at,
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.status, "received")

    def test_received_timestamp_is_normalized_to_utc(self) -> None:
        received_at = datetime.fromisoformat("2026-09-29T09:00:00-03:00")
        dream, _ = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=98,
            received_at=received_at,
        )

        self.assertEqual(dream.received_at, "2026-09-29T12:00:00+00:00")

    def test_dream_date_and_its_source_are_stored(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=97,
            dream_date=datetime(2026, 9, 29, tzinfo=timezone.utc).date(),
        )

        self.assertEqual(dream.dream_date, "2026-09-29")
        self.assertEqual(dream.dream_date_source, "received_at")

    def test_accepted_date_candidate_replaces_the_default_only_after_resolution(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=96,
            dream_date=datetime(2026, 9, 29, tzinfo=timezone.utc).date(),
        )
        pending = self.store.request_date_confirmation(
            dream.id,
            candidate_date=datetime(2026, 9, 28, tzinfo=timezone.utc).date(),
            candidate_source="narrated_relative_date",
            matched_text="ontem",
        )
        unchanged = self.store.get_by_id(dream.id)
        resolved = self.store.resolve_date_confirmation(dream.id, accept_candidate=True)

        self.assertEqual(pending.candidate_date, "2026-09-28")
        self.assertEqual(unchanged.dream_date, "2026-09-29")
        self.assertEqual(resolved.dream_date, "2026-09-28")
        self.assertEqual(resolved.dream_date_source, "narrated_confirmed")
        with self.assertRaises(LookupError):
            self.store.get_pending_date_confirmation(dream.id)

    def test_rejected_date_candidate_keeps_the_received_date(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram",
            source_chat_id=42,
            source_message_id=95,
            dream_date=datetime(2026, 9, 29, tzinfo=timezone.utc).date(),
        )
        self.store.request_date_confirmation(
            dream.id,
            candidate_date=datetime(2026, 9, 28, tzinfo=timezone.utc).date(),
            candidate_source="narrated_relative_date",
            matched_text="ontem",
        )
        resolved = self.store.resolve_date_confirmation(dream.id, accept_candidate=False)

        self.assertEqual(resolved.dream_date, "2026-09-29")
        self.assertEqual(resolved.dream_date_source, "received_at")

    def test_initialize_migrates_a_database_created_before_date_source(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.db"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE dreams (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL,
                    source_chat_id INTEGER NOT NULL, source_message_id INTEGER NOT NULL,
                    received_at TEXT NOT NULL, dream_date TEXT,
                    status TEXT NOT NULL, raw_transcript TEXT,
                    refined_transcript TEXT, document_url TEXT,
                    error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(source, source_chat_id, source_message_id)
                )
                """
            )

        legacy_store = DreamStore(legacy_path)
        legacy_store.initialize()
        with sqlite3.connect(legacy_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(dreams)")}

        self.assertIn("dream_date_source", columns)

    def test_happy_path_keeps_each_pipeline_artifact(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=100
        )
        transcribed = self.store.advance(
            dream.id, status="transcribed", raw_transcript="Eu estava em uma casa."
        )
        refined = self.store.advance(
            dream.id, status="refined", refined_transcript="Eu estava em uma casa."
        )
        published = self.store.advance(
            dream.id,
            status="published",
            document_url="https://docs.google.com/document/d/example/edit",
        )

        self.assertEqual(transcribed.raw_transcript, "Eu estava em uma casa.")
        self.assertEqual(refined.refined_transcript, "Eu estava em uma casa.")
        self.assertEqual(published.status, "published")
        self.assertTrue(published.document_url.startswith("https://docs.google.com/"))

    def test_list_published_excludes_unfinished_and_failed_dreams(self) -> None:
        published, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=200
        )
        self.store.advance(published.id, status="transcribed", raw_transcript="texto")
        self.store.advance(published.id, status="refined", refined_transcript="texto")
        self.store.advance(
            published.id, status="published", document_url="https://docs.google.com/document/d/published/edit"
        )
        unfinished, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=201
        )
        failed, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=202
        )
        self.store.mark_failed(failed.id, "erro de exemplo")

        dreams = self.store.list_published()

        self.assertEqual([dream.id for dream in dreams], [published.id])
        self.assertNotEqual(dreams[0].id, unfinished.id)

    def test_replacing_factual_tags_keeps_only_the_latest_keyword_tags(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=203
        )
        self.store.replace_factual_tags(dream.id, ["casa", "agua", "casa"])
        self.store.replace_factual_tags(dream.id, ["familia"])

        self.assertEqual(self.store.list_tags(dream.id), ["familia"])

    def test_filter_by_tag_returns_only_published_dreams_with_that_tag(self) -> None:
        published, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=204
        )
        self.store.advance(published.id, status="transcribed", raw_transcript="texto")
        self.store.advance(published.id, status="refined", refined_transcript="texto")
        self.store.advance(
            published.id, status="published", document_url="https://docs.google.com/document/d/tagged/edit"
        )
        self.store.replace_factual_tags(published.id, ["agua"])

        unfinished, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=205
        )
        self.store.replace_factual_tags(unfinished.id, ["agua"])

        self.assertEqual([dream.id for dream in self.store.list_published_by_tag("agua")], [published.id])

    def test_search_combines_period_text_and_tag_without_returning_unpublished(self) -> None:
        matching, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=206,
            dream_date=datetime(2026, 9, 10, tzinfo=timezone.utc).date(),
        )
        self.store.advance(matching.id, status="transcribed", raw_transcript="Eu atravessei um rio.")
        self.store.advance(matching.id, status="refined", refined_transcript="Eu atravessei um rio.")
        self.store.advance(
            matching.id, status="published", document_url="https://docs.google.com/document/d/matching/edit"
        )
        self.store.replace_factual_tags(matching.id, ["agua"])

        wrong_period, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=207,
            dream_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
        )
        self.store.advance(wrong_period.id, status="transcribed", raw_transcript="Eu atravessei um rio.")
        self.store.advance(wrong_period.id, status="refined", refined_transcript="Eu atravessei um rio.")
        self.store.advance(
            wrong_period.id, status="published", document_url="https://docs.google.com/document/d/old/edit"
        )
        self.store.replace_factual_tags(wrong_period.id, ["agua"])

        unfinished, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=208,
            dream_date=datetime(2026, 9, 11, tzinfo=timezone.utc).date(),
        )
        self.store.advance(unfinished.id, status="transcribed", raw_transcript="Eu atravessei um rio.")
        self.store.replace_factual_tags(unfinished.id, ["agua"])

        results = self.store.search_published(
            start_date=datetime(2026, 9, 1, tzinfo=timezone.utc).date(),
            end_date=datetime(2026, 9, 30, tzinfo=timezone.utc).date(),
            text="rio",
            tag="agua",
        )

        self.assertEqual([dream.id for dream in results], [matching.id])

    def test_cannot_skip_a_pipeline_stage(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=101
        )

        with self.assertRaisesRegex(ValueError, "Transição inválida"):
            self.store.advance(dream.id, status="published", document_url="https://example.test")

    def test_transcription_state_requires_a_non_empty_transcript(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=103
        )

        with self.assertRaisesRegex(ValueError, "transcrição não pode ser vazia"):
            self.store.advance(dream.id, status="transcribed", raw_transcript="")

    def test_failure_is_recorded_from_an_incomplete_stage(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=102
        )
        failed = self.store.mark_failed(dream.id, "Groq indisponível")

        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_message, "Groq indisponível")

    def test_google_publication_failure_can_be_retried_without_refining_again(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=300
        )
        self.store.advance(dream.id, status="transcribed", raw_transcript="texto bruto")
        self.store.advance(dream.id, status="refined", refined_transcript="texto refinado")
        self.store.mark_failed(dream.id, GOOGLE_PUBLICATION_FAILURE)

        pending = self.store.list_pending_publications()
        resumed = self.store.prepare_publication_retry(dream.id)

        self.assertEqual([item.id for item in pending], [dream.id])
        self.assertEqual(resumed.status, "refined")
        self.assertEqual(resumed.refined_transcript, "texto refinado")
        self.assertIsNone(resumed.error_message)

    def test_unrelated_failure_cannot_be_retried_as_google_publication(self) -> None:
        dream, _ = self.store.create_or_get_received(
            source="telegram", source_chat_id=42, source_message_id=301
        )
        self.store.mark_failed(dream.id, "Falha na etapa: transcrição")

        self.assertEqual(self.store.list_pending_publications(), [])
        with self.assertRaisesRegex(ValueError, "não está disponível"):
            self.store.prepare_publication_retry(dream.id)


if __name__ == "__main__":
    unittest.main()
