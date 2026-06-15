"""
backend/core/security.py
Camada de segurança: criptografia de campos sensíveis (PII) em repouso
e utilitários de mascaramento para logs.

Utiliza Fernet (AES-128-CBC + HMAC-SHA256) da biblioteca `cryptography`.
Cada campo sensível (CPF, nome, número de conta) é criptografado
individualmente antes de persistir no SQLite.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


# =====================================================================
# Criptografia Fernet — dados em repouso
# =====================================================================

class FieldEncryptor:
    """Criptografa e descriptografa campos individuais usando Fernet.

    A chave é carregada a partir do DB_ENCRYPTION_KEY no .env.
    Todos os dados são convertidos para bytes UTF-8 antes da criptografia
    e retornados como bytes (armazenados como LargeBinary/BLOB no SQLite).
    """

    def __init__(self, key: str) -> None:
        """
        Args:
            key: Chave Fernet em formato base64url (44 caracteres).
        """
        self._fernet = Fernet(key.encode("utf-8"))

    def encrypt(self, plaintext: Optional[str]) -> Optional[bytes]:
        """Criptografa um campo de texto.

        Args:
            plaintext: Texto a criptografar. Se None/vazio, retorna None.

        Returns:
            Token Fernet como bytes, ou None se entrada vazia.
        """
        if not plaintext:
            return None
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: Optional[bytes]) -> Optional[str]:
        """Descriptografa um campo.

        Args:
            ciphertext: Token Fernet como bytes.

        Returns:
            Texto original, ou None se entrada vazia ou inválida.
        """
        if not ciphertext:
            return None
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            return None


@lru_cache(maxsize=1)
def get_encryptor() -> FieldEncryptor:
    """Retorna singleton do encryptor com a chave do .env."""
    from backend.core.config import get_settings
    return FieldEncryptor(get_settings().db_encryption_key)


# =====================================================================
# Mascaramento de PII — para logs e outputs
# =====================================================================

# Patterns compilados para performance
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # CPF formatado: 123.456.789-00
    (re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), "***.***.***-**"),
    # CPF sem formatação (11 dígitos consecutivos)
    (re.compile(r"(?<!\d)\d{11}(?!\d)"), "***MASKED_CPF***"),
    # CNPJ formatado: 12.345.678/0001-00
    (re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"), "**.***.***/**MASKED**"),
    # CNPJ sem formatação (14 dígitos)
    (re.compile(r"(?<!\d)\d{14}(?!\d)"), "***MASKED_CNPJ***"),
    # E-mail
    (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "***MASKED_EMAIL***",
    ),
    # Número de conta com agência (ag 1234 cc 567890)
    (
        re.compile(r"(ag[êe]?ncia|ag\.?)\s*:?\s*\d{3,5}", re.IGNORECASE),
        "ag:****",
    ),
    (
        re.compile(r"(conta|cc|account)\s*:?\s*\d{4,}", re.IGNORECASE),
        "conta:****",
    ),
]


def mask_pii(text: str) -> str:
    """Mascara PII em uma string.

    Aplica todos os patterns de mascaramento em sequência.
    Útil para sanitizar mensagens de log e respostas de debug.

    Args:
        text: Texto possivelmente contendo PII.

    Returns:
        Texto com PII mascarado.
    """
    if not isinstance(text, str):
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_dict_pii(data: dict) -> dict:
    """Mascara PII recursivamente em um dicionário.

    Útil para sanitizar payloads antes de logar.

    Args:
        data: Dicionário a sanitizar.

    Returns:
        Cópia do dicionário com campos de texto mascarados.
    """
    masked = {}
    for key, value in data.items():
        if isinstance(value, str):
            masked[key] = mask_pii(value)
        elif isinstance(value, dict):
            masked[key] = mask_dict_pii(value)
        elif isinstance(value, list):
            masked[key] = [
                mask_dict_pii(item) if isinstance(item, dict)
                else mask_pii(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            masked[key] = value
    return masked
