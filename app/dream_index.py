"""Projeção determinística do índice do diário a partir do SQLite."""

from datetime import date
from typing import Iterable

from app.dream_store import Dream


def render_published_dream_index(dreams: Iterable[Dream]) -> str:
    """Renderiza somente fatos já persistidos; não resume nem interpreta relatos."""
    lines = ["📌 DIÁRIO DE SONHOS — ÍNDICE", "", "Registros publicados:", ""]
    published_dreams = list(dreams)
    if not published_dreams:
        lines.append("Nenhum sonho publicado até o momento.")
    else:
        for dream in published_dreams:
            formatted_date = date.fromisoformat(dream.dream_date).strftime("%d/%m/%Y")
            lines.append(f"• {formatted_date} — 🔖 dreamlistener:{dream.id}")
            lines.append(f"  {dream.document_url}")

    return "\n".join(lines) + "\n"
