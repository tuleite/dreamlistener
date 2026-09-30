"""Persistência local e auditável dos relatos de sonho.

O módulo não conhece Telegram, Groq, Gemini ou Google Docs. Essa separação
mantém a regra de negócio testável e permite retomar o processamento após uma
falha externa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator, Literal
from uuid import uuid4


DreamStatus = Literal["received", "transcribed", "refined", "published", "failed"]

VALID_STATUSES: set[str] = {
    "received",
    "transcribed",
    "refined",
    "published",
    "failed",
}

# Uma falha de OAuth ocorre depois que o texto já foi refinado. Ela pode ser
# retomada com segurança após um novo consentimento, sem reenviar o áudio.
GOOGLE_PUBLICATION_FAILURE = "Falha na etapa: publicação no Google Docs"

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "received": {"transcribed", "failed"},
    "transcribed": {"refined", "failed"},
    "refined": {"published", "failed"},
    "published": set(),
    "failed": set(),
}


@dataclass(frozen=True)
class Dream:
    id: str
    source: str
    source_chat_id: int
    source_message_id: int
    received_at: str
    dream_date: str | None
    dream_date_source: str
    status: DreamStatus
    raw_transcript: str | None
    refined_transcript: str | None
    document_url: str | None
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PendingDateConfirmation:
    dream_id: str
    candidate_date: str
    candidate_source: str
    matched_text: str
    created_at: str


class DreamStore:
    """Repositório SQLite de sonhos recebidos e suas transições de estado."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        """Cria a tabela e seus índices, sem apagar dados existentes."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dreams (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_chat_id INTEGER NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    received_at TEXT NOT NULL,
                    dream_date TEXT,
                    dream_date_source TEXT NOT NULL DEFAULT 'received_at',
                    status TEXT NOT NULL CHECK (status IN (
                        'received', 'transcribed', 'refined', 'published', 'failed'
                    )),
                    raw_transcript TEXT,
                    refined_transcript TEXT,
                    document_url TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source, source_chat_id, source_message_id)
                )
                """
            )
            self._ensure_dream_date_source_column(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_date_confirmations (
                    dream_id TEXT PRIMARY KEY,
                    candidate_date TEXT NOT NULL,
                    candidate_source TEXT NOT NULL,
                    matched_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (dream_id) REFERENCES dreams(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dream_tags (
                    dream_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (dream_id, tag, source),
                    FOREIGN KEY (dream_id) REFERENCES dreams(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_dreams_status ON dreams(status)"
            )

    def create_or_get_received(
        self,
        *,
        source: str,
        source_chat_id: int,
        source_message_id: int,
        received_at: datetime | None = None,
        dream_date: date | None = None,
    ) -> tuple[Dream, bool]:
        """Cria um sonho recebido ou devolve o existente para a mesma mensagem.

        O booleano indica se a linha foi criada agora. É a garantia de
        idempotência da entrada: tentativas repetidas não duplicam o relato.
        """
        timestamp = _to_utc_iso(received_at or datetime.now(timezone.utc))
        dream_id = str(uuid4())
        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO dreams (
                        id, source, source_chat_id, source_message_id, received_at,
                        dream_date, dream_date_source, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'received_at', 'received', ?, ?)
                    """,
                    (
                        dream_id,
                        source,
                        source_chat_id,
                        source_message_id,
                        timestamp,
                        dream_date.isoformat() if dream_date else None,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError:
                return (
                    self.get_by_source_message(
                        source=source,
                        source_chat_id=source_chat_id,
                        source_message_id=source_message_id,
                        connection=connection,
                    ),
                    False,
                )

            return self.get_by_id(dream_id, connection=connection), True

    def get_by_id(self, dream_id: str, *, connection: sqlite3.Connection | None = None) -> Dream:
        if connection is not None:
            row = connection.execute("SELECT * FROM dreams WHERE id = ?", (dream_id,)).fetchone()
            return _dream_from_row(row)
        with self._connect() as new_connection:
            return self.get_by_id(dream_id, connection=new_connection)

    def get_by_source_message(
        self,
        *,
        source: str,
        source_chat_id: int,
        source_message_id: int,
        connection: sqlite3.Connection | None = None,
    ) -> Dream:
        if connection is not None:
            row = connection.execute(
                """
                SELECT * FROM dreams
                WHERE source = ? AND source_chat_id = ? AND source_message_id = ?
                """,
                (source, source_chat_id, source_message_id),
            ).fetchone()
            return _dream_from_row(row)
        with self._connect() as new_connection:
            return self.get_by_source_message(
                source=source,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                connection=new_connection,
            )

    def advance(
        self,
        dream_id: str,
        *,
        status: DreamStatus,
        raw_transcript: str | None = None,
        refined_transcript: str | None = None,
        document_url: str | None = None,
    ) -> Dream:
        """Registra uma transição válida e os dados produzidos naquele estágio."""
        current = self.get_by_id(dream_id)
        if status not in ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"Transição inválida: {current.status!r} → {status!r}")

        if status == "transcribed" and not raw_transcript:
            raise ValueError("Uma transcrição não pode ser vazia.")
        if status == "refined" and not refined_transcript:
            raise ValueError("Um texto refinado não pode ser vazio.")
        if status == "published" and not document_url:
            raise ValueError("Uma publicação exige a URL do documento.")

        now = _to_utc_iso(datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE dreams
                SET status = ?, raw_transcript = COALESCE(?, raw_transcript),
                    refined_transcript = COALESCE(?, refined_transcript),
                    document_url = COALESCE(?, document_url), updated_at = ?
                WHERE id = ?
                """,
                (status, raw_transcript, refined_transcript, document_url, now, dream_id),
            )
            return self.get_by_id(dream_id, connection=connection)

    def mark_failed(self, dream_id: str, error_message: str) -> Dream:
        """Registra uma falha sem armazenar stack trace ou dados de credenciais."""
        current = self.get_by_id(dream_id)
        if "failed" not in ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"Não é possível falhar um sonho em {current.status!r}.")
        if not error_message.strip():
            raise ValueError("A falha precisa de uma mensagem resumida.")

        now = _to_utc_iso(datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE dreams SET status = 'failed', error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (error_message.strip(), now, dream_id),
            )
            return self.get_by_id(dream_id, connection=connection)

    def list_published(self) -> list[Dream]:
        """Lista a fonte estruturada para projeções de leitura, como o índice."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM dreams
                WHERE status = 'published'
                ORDER BY dream_date IS NULL, dream_date DESC, received_at DESC
                """
            ).fetchall()
            return [_dream_from_row(row) for row in rows]

    def list_pending_publications(self) -> list[Dream]:
        """Lista textos refinados que podem ser publicados ou retomados.

        Inclui registros antigos marcados como falha apenas quando a falha foi
        a publicação no Google Docs. Outras falhas continuam exigindo uma
        decisão explícita, pois podem significar transcrição ou dados inválidos.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM dreams
                WHERE status = 'refined'
                   OR (
                        status = 'failed'
                    AND error_message = ?
                    AND refined_transcript IS NOT NULL
                   )
                ORDER BY received_at ASC
                """,
                (GOOGLE_PUBLICATION_FAILURE,),
            ).fetchall()
            return [_dream_from_row(row) for row in rows]

    def prepare_publication_retry(self, dream_id: str) -> Dream:
        """Restaura somente uma falha conhecida de publicação para `refined`.

        Essa transição excepcional é deliberadamente estreita: ela não permite
        ressuscitar erros de transcrição/refinamento nem registros publicados.
        """
        current = self.get_by_id(dream_id)
        if current.status == "refined":
            return current
        if (
            current.status != "failed"
            or current.error_message != GOOGLE_PUBLICATION_FAILURE
            or not current.refined_transcript
        ):
            raise ValueError("Este sonho não está disponível para retomar a publicação.")

        now = _to_utc_iso(datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE dreams
                SET status = 'refined', error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, dream_id),
            )
            return self.get_by_id(dream_id, connection=connection)

    def replace_factual_tags(self, dream_id: str, tags: list[str]) -> None:
        """Substitui apenas as tags produzidas pela taxonomia determinística."""
        self.get_by_id(dream_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM dream_tags WHERE dream_id = ? AND source = 'keyword'", (dream_id,)
            )
            connection.executemany(
                "INSERT INTO dream_tags (dream_id, tag, source) VALUES (?, ?, 'keyword')",
                [(dream_id, tag) for tag in sorted(set(tags))],
            )

    def list_tags(self, dream_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT tag FROM dream_tags WHERE dream_id = ? ORDER BY tag", (dream_id,)
            ).fetchall()
            return [row["tag"] for row in rows]

    def list_published_by_tag(self, tag: str) -> list[Dream]:
        """Busca registros publicados por uma tag factual canônica."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT dreams.* FROM dreams
                JOIN dream_tags ON dream_tags.dream_id = dreams.id
                WHERE dreams.status = 'published' AND dream_tags.tag = ?
                ORDER BY dreams.dream_date DESC, dreams.received_at DESC
                """,
                (tag,),
            ).fetchall()
            return [_dream_from_row(row) for row in rows]

    def search_published(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        text: str | None = None,
        tag: str | None = None,
    ) -> list[Dream]:
        """Busca sonhos publicados por período, termo literal e/ou tag factual."""
        query = ["SELECT DISTINCT dreams.* FROM dreams"]
        parameters: list[str] = []
        if tag:
            query.append("JOIN dream_tags ON dream_tags.dream_id = dreams.id")

        clauses = ["dreams.status = 'published'"]
        if start_date:
            clauses.append("dreams.dream_date >= ?")
            parameters.append(start_date.isoformat())
        if end_date:
            clauses.append("dreams.dream_date <= ?")
            parameters.append(end_date.isoformat())
        if text and text.strip():
            clauses.append("(dreams.raw_transcript LIKE ? OR dreams.refined_transcript LIKE ?)")
            pattern = f"%{text.strip()}%"
            parameters.extend([pattern, pattern])
        if tag:
            clauses.append("dream_tags.tag = ?")
            parameters.append(tag)

        query.append("WHERE " + " AND ".join(clauses))
        query.append("ORDER BY dreams.dream_date DESC, dreams.received_at DESC")
        with self._connect() as connection:
            rows = connection.execute(" ".join(query), parameters).fetchall()
            return [_dream_from_row(row) for row in rows]

    def request_date_confirmation(
        self,
        dream_id: str,
        *,
        candidate_date: date,
        candidate_source: str,
        matched_text: str,
    ) -> PendingDateConfirmation:
        """Guarda uma candidata sem alterar a data oficial do sonho."""
        self.get_by_id(dream_id)
        now = _to_utc_iso(datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pending_date_confirmations (
                    dream_id, candidate_date, candidate_source, matched_text, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(dream_id) DO UPDATE SET
                    candidate_date = excluded.candidate_date,
                    candidate_source = excluded.candidate_source,
                    matched_text = excluded.matched_text,
                    created_at = excluded.created_at
                """,
                (dream_id, candidate_date.isoformat(), candidate_source, matched_text, now),
            )
            return self.get_pending_date_confirmation(dream_id, connection=connection)

    def get_pending_date_confirmation(
        self, dream_id: str, *, connection: sqlite3.Connection | None = None
    ) -> PendingDateConfirmation:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM pending_date_confirmations WHERE dream_id = ?", (dream_id,)
            ).fetchone()
            if row is None:
                raise LookupError("Nenhuma confirmação de data pendente para este sonho.")
            return PendingDateConfirmation(**dict(row))
        with self._connect() as new_connection:
            return self.get_pending_date_confirmation(dream_id, connection=new_connection)

    def resolve_date_confirmation(self, dream_id: str, *, accept_candidate: bool) -> Dream:
        """Confirma ou rejeita a candidata e remove a pendência correspondente."""
        with self._connect() as connection:
            pending = self.get_pending_date_confirmation(dream_id, connection=connection)
            if accept_candidate:
                connection.execute(
                    """
                    UPDATE dreams
                    SET dream_date = ?, dream_date_source = 'narrated_confirmed', updated_at = ?
                    WHERE id = ?
                    """,
                    (pending.candidate_date, _to_utc_iso(datetime.now(timezone.utc)), dream_id),
                )
            connection.execute("DELETE FROM pending_date_confirmations WHERE dream_id = ?", (dream_id,))
            return self.get_by_id(dream_id, connection=connection)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _ensure_dream_date_source_column(connection: sqlite3.Connection) -> None:
        """Aplica uma migração aditiva para bancos criados antes dessa coluna."""
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(dreams)").fetchall()
        }
        if "dream_date_source" not in columns:
            connection.execute(
                "ALTER TABLE dreams ADD COLUMN dream_date_source TEXT NOT NULL DEFAULT 'received_at'"
            )


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Timestamps precisam incluir fuso horário.")
    return value.astimezone(timezone.utc).isoformat()


def _dream_from_row(row: sqlite3.Row | None) -> Dream:
    if row is None:
        raise LookupError("Sonho não encontrado.")
    return Dream(**dict(row))
