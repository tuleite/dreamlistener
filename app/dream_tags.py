"""Tags factuais baseadas em menções observáveis no relato, sem interpretação."""

import re
import unicodedata


TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agua": ("agua", "mar", "rio", "lago", "chuva", "piscina"),
    "casa": ("casa", "apartamento", "quarto", "cozinha", "sala"),
    "familia": ("mae", "pai", "irma", "irmao", "filho", "filha", "avo", "familia"),
    "trabalho": ("trabalho", "emprego", "chefe", "escritorio", "reuniao"),
    "escola": ("escola", "faculdade", "aula", "professor", "prova"),
    "transporte": ("carro", "onibus", "aviao", "trem", "metro", "bicicleta"),
    "animal": ("cachorro", "gato", "passaro", "cobra", "cavalo", "peixe"),
    "natureza": ("floresta", "arvore", "praia", "montanha", "jardim"),
}


def extract_factual_tags(text: str) -> list[str]:
    """Retorna tags canônicas quando uma de suas palavras-chave é mencionada."""
    normalized = _normalize(text)
    return [
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords)
    ]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_accents
