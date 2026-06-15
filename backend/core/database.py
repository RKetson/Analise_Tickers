"""
backend/core/database.py
Engine SQLAlchemy e gerenciamento de sessão para SQLite.

O banco vive em data/pluggy_db.sqlite (mesmo diretório de dados do
projeto Streamlit). Tabelas são criadas automaticamente na
inicialização se não existirem.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

# =====================================================================
# Engine singleton
# =====================================================================

_engine = None
_SessionLocal = None


def _get_engine():
    """Cria ou retorna o engine SQLAlchemy singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},  # SQLite + threads
            pool_pre_ping=True,
        )

        # Habilitar WAL mode para melhor concorrência em SQLite
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return _engine


def _get_session_factory() -> sessionmaker:
    """Retorna a session factory singleton."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


# =====================================================================
# Context managers
# =====================================================================

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager que fornece uma sessão transacional.

    Exemplo de uso:
        with get_db_session() as session:
            session.add(item)
            # commit automático ao sair do bloco sem exceção

    Em caso de exceção, faz rollback automaticamente.
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session_dependency() -> Generator[Session, None, None]:
    """Dependency injection para FastAPI.

    Uso em routes:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db_session_dependency)):
            ...
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =====================================================================
# Inicialização
# =====================================================================

def init_db() -> None:
    """Cria todas as tabelas no banco se não existirem.

    Importa os modelos para registrar no metadata do Base e então
    executa create_all().
    """
    from backend.models.db_models import Base  # noqa: F401 — registra modelos

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
