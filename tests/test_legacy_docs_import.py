import unittest
from pathlib import Path
import tempfile

from app.dream_store import DreamStore
from app.legacy_docs_import import (
    apply_legacy_import,
    build_legacy_import_preview,
    render_preview,
)


def tab(title: str, tab_id: str, text: str) -> dict:
    return {
        "tabProperties": {"title": title, "tabId": tab_id},
        "documentTab": {"body": {"content": [{
            "paragraph": {"elements": [{"textRun": {"content": text}}]}
        }]}},
    }


class LegacyDocsImportTest(unittest.TestCase):
    def test_extracts_unmarked_entries_from_dated_tabs(self) -> None:
        document = {"tabs": [tab(
            "30/09/2026", "tab-1",
            "🗓️ Voz_10 — Registrado às 08:30\nEu estava em uma casa perto do rio.\n⎯⎯⎯\n\n"
            "🗓️ Registrado às 09:00\nEu via uma floresta.\n⎯⎯⎯\n",
        )]}

        preview = build_legacy_import_preview(document, document_id="document-1")

        self.assertEqual(len(preview.candidates), 2)
        self.assertEqual(preview.candidates[0].dream_date.isoformat(), "2026-09-30")
        self.assertEqual(preview.candidates[0].registered_time, "08:30")
        self.assertEqual(preview.candidates[0].refined_transcript, "Eu estava em uma casa perto do rio.")
        self.assertNotEqual(preview.candidates[0].source_message_id, preview.candidates[1].source_message_id)

    def test_extracts_an_entry_identified_by_its_legacy_whatsapp_filename(self) -> None:
        document = {"tabs": [tab(
            "01/09/2026", "tab-legacy",
            "🗓️ WhatsApp Ptt 2026-09-01 at 15.19.34.ogg — Registrado às 19:47\n"
            "Eu contava um sonho antigo.\n⎯⎯⎯\n",
        )]}

        preview = build_legacy_import_preview(document, document_id="document-legacy")

        self.assertEqual(len(preview.candidates), 1)
        self.assertEqual(preview.candidates[0].registered_time, "19:47")
        self.assertEqual(preview.candidates[0].refined_transcript, "Eu contava um sonho antigo.")

    def test_ignores_index_and_entries_already_marked_by_the_app(self) -> None:
        document = {"tabs": [
            tab("📌 Índice & Análises", "index", "texto de índice"),
            tab(
                "30/09/2026", "tab-1",
                "🗓️ Voz_11 — Registrado às 10:00\n"
                "🔖 dreamlistener:12345678-1234-1234-1234-123456789abc\n"
                "Um sonho já importado.\n⎯⎯⎯\n",
            ),
        ]}

        preview = build_legacy_import_preview(document, document_id="document-1")

        self.assertEqual(preview.candidates, ())
        self.assertEqual(preview.ignored_tabs, ("📌 Índice & Análises",))
        self.assertEqual(preview.skipped_marked_entries, 1)

    def test_preview_hides_transcript_unless_the_user_explicitly_requests_it(self) -> None:
        document = {"tabs": [tab(
            "30/09/2026", "tab-1", "🗓️ Registrado às 08:30\nTexto privado.\n⎯⎯⎯\n"
        )]}
        preview = build_legacy_import_preview(document, document_id="document-1")

        output = render_preview(preview, show_candidates=True)

        self.assertNotIn("Texto privado", output)
        self.assertIn("30/09/2026 às 08:30", output)

    def test_apply_import_creates_backup_tags_and_is_idempotent(self) -> None:
        document = {"tabs": [tab(
            "30/09/2026", "tab-1", "🗓️ Registrado às 08:30\nEu estava em uma casa perto do rio.\n⎯⎯⎯\n"
        )]}
        preview = build_legacy_import_preview(document, document_id="document-1")
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "dreamlistener.db"
            store = DreamStore(database_path)
            first = apply_legacy_import(
                store, preview,
                document_url="https://docs.google.com/document/d/example/edit",
                backup_directory=Path(temporary_directory) / "backups",
            )
            second = apply_legacy_import(
                store, preview,
                document_url="https://docs.google.com/document/d/example/edit",
                backup_directory=Path(temporary_directory) / "backups",
            )

            imported = store.list_published()
            self.assertEqual(first.imported_count, 1)
            self.assertTrue(first.backup_path and first.backup_path.exists())
            self.assertEqual(second.imported_count, 0)
            self.assertIsNone(second.backup_path)
            self.assertEqual(len(imported), 1)
            self.assertEqual(store.list_tags(imported[0].id), ["agua", "casa"])
