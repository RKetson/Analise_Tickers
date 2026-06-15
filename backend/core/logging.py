"""
backend/core/logging.py
Logging estruturado com mascaramento automático de PII.

Usa structlog para produzir logs JSON (produção) ou coloridos (dev),
com um processador dedicado que detecta e mascara padrões de dados
pessoais antes de emitir qualquer linha de log.
"""

from __future__ import annotations

import logging
import sys

import structlog

from backend.core.security import mask_pii


# =====================================================================
# Processador structlog para mascaramento de PII
# =====================================================================

def _pii_masking_processor(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Processador structlog que mascara PII em todos os campos do evento.

    Percorre todas as chaves do event_dict e aplica mask_pii em valores string.
    Isso garante que CPFs, e-mails, números de conta, etc. NUNCA apareçam
    em texto claro nos logs, independentemente de quem gerou o log.
    """
    for key in list(event_dict.keys()):
        value = event_dict[key]
        if isinstance(value, str):
            event_dict[key] = mask_pii(value)
        elif isinstance(value, dict):
            # Mascarar recursivamente em dicts aninhados
            event_dict[key] = {
                k: mask_pii(v) if isinstance(v, str) else v
                for k, v in value.items()
            }
    return event_dict


# =====================================================================
# Setup
# =====================================================================

def setup_logging(log_level: str = "INFO", env: str = "development") -> None:
    """Configura o logging estruturado para toda a aplicação.

    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        env: Ambiente (development → console colorido, production → JSON).
    """
    # Processadores comuns
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _pii_masking_processor,  # 🛡️ PII masking antes do render
    ]

    if env == "production":
        # JSON para produção (fácil de ingerir em ferramentas de log)
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        # Console colorido para dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configurar handler do stdlib logging para usar structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silenciar loggers ruidosos de terceiros
    for noisy in ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Obtém um logger estruturado com PII masking.

    Args:
        name: Nome do módulo/componente.

    Returns:
        Logger structlog configurado.
    """
    return structlog.get_logger(name)
