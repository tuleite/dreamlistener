"""Interpretação determinística dos filtros do comando Telegram `/buscar`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import shlex


@dataclass(frozen=True)
class SearchCriteria:
    start_date: date | None = None
    end_date: date | None = None
    tag: str | None = None
    text: str | None = None


def parse_search_criteria(arguments: list[str]) -> SearchCriteria:
    """Converte filtros simples em critérios tipados, sem gerar SQL.

    Palavras que não são filtros formam a busca textual. Datas usam o formato
    ISO para evitar ambiguidade entre dia e mês: `de:2026-09-01`.
    """
    try:
        tokens = shlex.split(" ".join(arguments))
    except ValueError as error:
        raise ValueError("Aspas não foram fechadas na busca.") from error

    filters: dict[str, str] = {}
    text_tokens: list[str] = []
    for token in tokens:
        name, separator, value = token.partition(":")
        if separator and name in {"de", "ate", "tag"}:
            if not value:
                raise ValueError(f"O filtro `{name}:` precisa de um valor.")
            if name in filters:
                raise ValueError(f"O filtro `{name}:` só pode aparecer uma vez.")
            filters[name] = value
        else:
            text_tokens.append(token)

    start_date = _parse_date(filters.get("de"), "de")
    end_date = _parse_date(filters.get("ate"), "ate")
    if start_date and end_date and start_date > end_date:
        raise ValueError("A data `de:` não pode ser posterior à data `ate:`.")

    tag = filters.get("tag")
    if tag and not tag.replace("_", "").isalpha():
        raise ValueError("A tag deve conter apenas letras e `_`.")

    text = " ".join(text_tokens).strip() or None
    return SearchCriteria(start_date=start_date, end_date=end_date, tag=tag, text=text)


def _parse_date(value: str | None, filter_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"A data em `{filter_name}:` deve usar AAAA-MM-DD, por exemplo 2026-09-30."
        ) from error
