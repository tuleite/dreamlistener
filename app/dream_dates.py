"""Extração conservadora de referências de data em relatos em português."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo


APPLICATION_TIMEZONE = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class DreamDateCandidate:
    """Uma data explícita encontrada no texto, ainda sujeita à confirmação."""

    value: date
    source: str
    matched_text: str


def received_date_in_application_timezone(received_at: datetime) -> date:
    """Converte o instante de recebimento para a data civil do diário."""
    if received_at.tzinfo is None:
        raise ValueError("A data de recebimento precisa incluir fuso horário.")
    return received_at.astimezone(APPLICATION_TIMEZONE).date()


def extract_narrated_dream_date(
    text: str, received_at: datetime
) -> DreamDateCandidate | None:
    """Encontra uma única referência de data inequívoca no relato.

    O retorno é uma candidata, nunca uma atualização automática do diário.
    Datas sem ano e expressões vagas são deliberadamente ignoradas para evitar
    inferências silenciosas.
    """
    if received_at.tzinfo is None:
        raise ValueError("A data de recebimento precisa incluir fuso horário.")

    numeric_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if numeric_match:
        day, month, year = (int(part) for part in numeric_match.groups())
        try:
            return DreamDateCandidate(
                value=date(year, month, day),
                source="narrated_explicit_date",
                matched_text=numeric_match.group(0),
            )
        except ValueError:
            # Uma data inválida não deve produzir uma candidata aproximada.
            return None

    normalized_text = text.casefold()
    received_date = received_date_in_application_timezone(received_at)
    relative_dates = (
        (r"\banteontem\b", 2),
        (r"\bontem\b", 1),
        (r"\bhoje\b", 0),
    )
    for pattern, days_before in relative_dates:
        relative_match = re.search(pattern, normalized_text)
        if relative_match:
            return DreamDateCandidate(
                value=received_date - timedelta(days=days_before),
                source="narrated_relative_date",
                matched_text=relative_match.group(0),
            )

    return None
