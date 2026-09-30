"""Controle de acesso simples por chat do Telegram para o modo diário pessoal."""


def parse_allowed_chat_ids(value: str | None) -> frozenset[int]:
    """Lê uma lista separada por vírgulas e falha em configuração inválida."""
    if not value or not value.strip():
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise ValueError("ALLOWED_TELEGRAM_CHAT_IDS deve conter apenas números separados por vírgula.") from error


def is_allowed_chat(chat_id: int | None, allowed_chat_ids: frozenset[int]) -> bool:
    """Sem configuração, negar acesso é mais seguro do que permitir acesso aberto."""
    return chat_id is not None and chat_id in allowed_chat_ids
