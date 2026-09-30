"""Funções puras para manter o Google Docs como projeção idempotente."""

INDEX_PLACEHOLDER = "{{DREAMLISTENER_INDEX}}"

def dream_marker(dream_id: str) -> str:
    return f"dreamlistener:{dream_id}"


def document_contains_marker(document: dict, marker: str) -> bool:
    """Verifica se qualquer guia do documento já contém o marcador do sonho."""
    return any(marker in text for text in _tab_texts(document.get("tabs", [])))


def index_replacement_request(tab_id: str, index_text: str) -> dict:
    return {
        "replaceAllText": {
            "containsText": {"text": INDEX_PLACEHOLDER, "matchCase": True},
            "replaceText": f"{index_text}\n{INDEX_PLACEHOLDER}",
            "tabsCriteria": {"tabIds": [tab_id]},
        }
    }


def _tab_texts(tabs: list[dict]):
    for tab in tabs:
        body = tab.get("documentTab", {}).get("body", {})
        for element in body.get("content", []):
            paragraph = element.get("paragraph", {})
            for paragraph_element in paragraph.get("elements", []):
                yield paragraph_element.get("textRun", {}).get("content", "")
        yield from _tab_texts(tab.get("childTabs", []))
