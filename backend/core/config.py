"""
backend/core/config.py
Configurações centrais carregadas via variáveis de ambiente (.env).

Utiliza pydantic-settings para validação de tipos e falha rápida
caso variáveis obrigatórias estejam ausentes.

Suporte a Docker Secrets: se o valor de uma variável apontar para
um arquivo existente (ex: /run/secrets/pluggy_client_id), lê o
conteúdo do arquivo automaticamente.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do backend (onde vive o .env)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Diretório de dados compartilhado com o projeto Streamlit existente
DATA_DIR = _PROJECT_ROOT / "data"


class Settings(BaseSettings):
    """Configurações validadas do backend.

    Valores são lidos do .env na raiz de backend/ ou de variáveis
    de ambiente do sistema operacional.
    """

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Pluggy.ai ---
    pluggy_client_id: str = Field(
        ..., description="Client ID da conta Pluggy.ai"
    )
    pluggy_client_secret: str = Field(
        ..., description="Client Secret da conta Pluggy.ai"
    )
    pluggy_base_url: str = Field(
        default="https://api.pluggy.ai",
        description="Base URL da API Pluggy",
    )

    # --- Criptografia ---
    db_encryption_key: str = Field(
        ...,
        description=(
            "Chave Fernet para criptografia de PII em repouso. "
            "Gere com: python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ),
    )

    # --- Banco de dados ---
    database_url: str = Field(
        default=f"sqlite:///{DATA_DIR / 'pluggy_db.sqlite'}",
        description="URL de conexão SQLAlchemy",
    )

    # --- Ambiente ---
    app_env: Literal["development", "production"] = Field(default="development")
    log_level: str = Field(default="INFO")

    # --- Sincronização ---
    sync_interval_minutes: int = Field(
        default=0,
        description="Intervalo de sync automático em minutos (0 = desabilitado)",
    )

    # -----------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------
    @field_validator("pluggy_client_id", "pluggy_client_secret", "db_encryption_key")
    @classmethod
    def _resolve_docker_secret(cls, v: str) -> str:
        """Se o valor apontar para um arquivo existente, lê o conteúdo."""
        if v and os.path.isfile(v):
            return Path(v).read_text(encoding="utf-8").strip()
        return v

    @field_validator("db_encryption_key")
    @classmethod
    def _validate_fernet_key(cls, v: str) -> str:
        """Valida que a chave é uma Fernet key válida (44 bytes base64)."""
        if not v:
            raise ValueError("DB_ENCRYPTION_KEY não pode estar vazia")
        # Fernet key tem 44 bytes base64url
        import base64
        try:
            decoded = base64.urlsafe_b64decode(v)
            if len(decoded) != 32:
                raise ValueError
        except Exception:
            raise ValueError(
                "DB_ENCRYPTION_KEY inválida. Gere uma nova com: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância singleton das configurações.

    Falha imediatamente na inicialização se variáveis obrigatórias
    (PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET, DB_ENCRYPTION_KEY) não
    estiverem definidas.
    """
    return Settings()  # type: ignore[call-arg]
