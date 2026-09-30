"""Catálogo de comandos e texto de ajuda do Dreamlistener."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotCommandInfo:
    command: str
    description: str


COMMANDS = (
    BotCommandInfo("start", "Apresenta o Dreamlistener"),
    BotCommandInfo("ajuda", "Mostra os comandos e exemplos"),
    BotCommandInfo("buscar", "Busca sonhos publicados"),
    BotCommandInfo("retomar_publicacoes", "Retoma publicações após renovar o Google"),
)


def render_help() -> str:
    """Explica o fluxo sem esconder a diferença entre busca e interpretação."""
    return (
        "🌙 Comandos do Dreamlistener\n\n"
        "/buscar <texto> — procura no texto de sonhos publicados.\n"
        "/buscar tag:casa — filtra por uma tag factual.\n"
        "/buscar de:2026-09-01 ate:2026-09-30 — filtra por período.\n"
        "/buscar \"casa antiga\" tag:casa — combina filtros e uma frase.\n\n"
        "/retomar_publicacoes — use somente depois de renovar o consentimento do Google no computador onde o bot roda.\n\n"
        "A busca atual não interpreta sonhos, não usa RAG e só mostra registros publicados."
    )
