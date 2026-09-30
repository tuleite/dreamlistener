"""Leitura e prévia de importação do Diário de Sonhos legado.

Este módulo não grava no SQLite nem modifica o Google Docs. Ele existe para
transformar a estrutura semi-formatada do documento em candidatos revisáveis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import argparse
import re

HEADER_PATTERN = re.compile(
    r"^🗓️(?:\s+(?P<identifier>[^\n]+?)\s+—)?\s*Registrado às (?P<hour>\d{2}:\d{2})\n"
    r"(?P<body>.*?)(?=^🗓️|\Z)",
    flags=re.MULTILINE | re.DOTALL,
)
DIVIDER_PATTERN = re.compile(r"\n?⎯+\s*$")
MARKER_PATTERN = re.compile(r"dreamlistener:[0-9a-f-]{36}")


@dataclass(frozen=True)
class LegacyDreamCandidate:
    import_key: str
    source_message_id: int
    tab_title: str
    dream_date: date
    registered_time: str
    refined_transcript: str


@dataclass(frozen=True)
class LegacyImportPreview:
    candidates: tuple[LegacyDreamCandidate, ...]
    ignored_tabs: tuple[str, ...]
    skipped_marked_entries: int


def build_legacy_import_preview(document: dict, *, document_id: str) -> LegacyImportPreview:
    """Extrai candidatos somente de abas datadas e sem marcador do app."""
    candidates: list[LegacyDreamCandidate] = []
    ignored_tabs: list[str] = []
    skipped_marked_entries = 0

    for tab in _flatten_tabs(document.get("tabs", [])):
        properties = tab.get("tabProperties", {})
        title = properties.get("title", "sem título")
        tab_date = _parse_tab_date(title)
        if tab_date is None:
            ignored_tabs.append(title)
            continue

        text = _tab_text(tab)
        for position, match in enumerate(HEADER_PATTERN.finditer(text), start=1):
            body = DIVIDER_PATTERN.sub("", match.group("body")).strip()
            if not body:
                continue
            if MARKER_PATTERN.search(match.group(0)):
                skipped_marked_entries += 1
                continue

            import_key = _legacy_key(document_id, properties.get("tabId", title), position, body)
            candidates.append(
                LegacyDreamCandidate(
                    import_key=import_key,
                    source_message_id=_source_message_id(import_key),
                    tab_title=title,
                    dream_date=tab_date,
                    registered_time=match.group("hour"),
                    refined_transcript=body,
                )
            )

    return LegacyImportPreview(
        candidates=tuple(candidates),
        ignored_tabs=tuple(ignored_tabs),
        skipped_marked_entries=skipped_marked_entries,
    )


def fetch_existing_diary_document() -> tuple[str, str, dict]:
    """Lê o diário existente, sem criá-lo quando estiver ausente."""
    from googleapiclient.discovery import build

    from app.export_docs import NOME_DOCUMENTO_PADRAO, autenticar_google

    credentials = autenticar_google()
    drive_service = build("drive", "v3", credentials=credentials)
    docs_service = build("docs", "v1", credentials=credentials)
    query = (
        f"name = '{NOME_DOCUMENTO_PADRAO}' and "
        "mimeType = 'application/vnd.google-apps.document' and trashed = false"
    )
    files = drive_service.files().list(q=query, fields="files(id, name)").execute().get("files", [])
    if not files:
        raise LookupError(f"Documento '{NOME_DOCUMENTO_PADRAO}' não encontrado no Google Drive.")

    document_id = files[0]["id"]
    document_url = f"https://docs.google.com/document/d/{document_id}/edit"
    document = docs_service.documents().get(
        documentId=document_id, includeTabsContent=True
    ).execute()
    return document_id, document_url, document


def render_preview(preview: LegacyImportPreview, *, show_candidates: bool = False) -> str:
    """Gera uma prévia sem expor o texto dos sonhos por padrão."""
    lines = [
        "Prévia de importação (nenhuma alteração foi feita).",
        f"Candidatos legados encontrados: {len(preview.candidates)}",
        f"Entradas já marcadas pelo app e ignoradas: {preview.skipped_marked_entries}",
        f"Abas ignoradas por não terem data: {len(preview.ignored_tabs)}",
    ]
    if show_candidates:
        lines.append("")
        lines.append("Candidatos:")
        for candidate in preview.candidates:
            lines.append(
                f"- {candidate.dream_date:%d/%m/%Y} às {candidate.registered_time} "
                f"| aba {candidate.tab_title} | chave {candidate.import_key[:12]}"
            )
    return "\n".join(lines)


def _parse_tab_date(title: str) -> date | None:
    try:
        return date.fromisoformat("-".join(reversed(title.split("/"))))
    except ValueError:
        return None


def _flatten_tabs(tabs: list[dict]):
    for tab in tabs:
        yield tab
        yield from _flatten_tabs(tab.get("childTabs", []))


def _tab_text(tab: dict) -> str:
    content = tab.get("documentTab", {}).get("body", {}).get("content", [])
    fragments: list[str] = []
    for element in content:
        for paragraph_element in element.get("paragraph", {}).get("elements", []):
            fragments.append(paragraph_element.get("textRun", {}).get("content", ""))
    return "".join(fragments)


def _legacy_key(document_id: str, tab_id: str, position: int, body: str) -> str:
    payload = f"{document_id}|{tab_id}|{position}|{body}".encode("utf-8")
    return sha256(payload).hexdigest()


def _source_message_id(import_key: str) -> int:
    """Gera um inteiro SQLite seguro e estável para a chave de idempotência."""
    return int(import_key[:16], 16) & ((1 << 63) - 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mostra uma prévia do diário legado no Google Docs.")
    parser.add_argument("--show-candidates", action="store_true", help="Mostra data e chave de cada candidato.")
    arguments = parser.parse_args()

    document_id, document_url, document = fetch_existing_diary_document()
    preview = build_legacy_import_preview(document, document_id=document_id)
    print(f"Diário: {document_url}")
    print(render_preview(preview, show_candidates=arguments.show_candidates))


if __name__ == "__main__":
    main()
