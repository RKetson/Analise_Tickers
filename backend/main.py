"""
backend/main.py
Entry point da aplicação FastAPI — Analisador Financeiro.

Inicializa:
    - Logging estruturado com PII masking
    - Banco de dados SQLite (cria tabelas se não existirem)
    - Router de endpoints REST
    - APScheduler para sincronização periódica (se configurado)
    - CORS para integração com frontend Streamlit
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.core.config import get_settings
from backend.core.database import init_db
from backend.core.logging import get_logger, setup_logging


# =====================================================================
# Lifespan (startup / shutdown)
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    settings = get_settings()

    # 1. Setup logging
    setup_logging(log_level=settings.log_level, env=settings.app_env)
    logger = get_logger("main")
    logger.info(
        "startup",
        app_env=settings.app_env,
        database=settings.database_url,
    )

    # 2. Criar tabelas no banco
    init_db()
    logger.info("database_initialized")

    # 3. Scheduler opcional
    scheduler = None
    if settings.sync_interval_minutes > 0:
        scheduler = _start_scheduler(settings.sync_interval_minutes)
        logger.info(
            "scheduler_started",
            interval_minutes=settings.sync_interval_minutes,
        )

    yield  # Aplicação rodando

    # Shutdown
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

    logger.info("shutdown_complete")


def _start_scheduler(interval_minutes: int):
    """Inicia APScheduler para sincronização periódica."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from backend.core.database import get_db_session
    from backend.models.db_models import PluggyItem
    from backend.services.sync_service import SyncService

    scheduler = AsyncIOScheduler()

    async def _periodic_sync():
        """Sincroniza todos os Items registrados."""
        logger = get_logger("scheduler")
        sync_service = SyncService()

        with get_db_session() as session:
            items = session.query(PluggyItem).all()
            item_ids = [item.id for item in items]

        for item_id in item_ids:
            try:
                with get_db_session() as session:
                    await sync_service.incremental_sync(session, item_id)
            except Exception as e:
                logger.error(
                    "periodic_sync_error",
                    item_id=item_id,
                    error=str(e),
                )

    scheduler.add_job(
        _periodic_sync,
        "interval",
        minutes=interval_minutes,
        id="pluggy_sync",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


# =====================================================================
# FastAPI App
# =====================================================================

app = FastAPI(
    title="ValuaçãoBR — Analisador Financeiro",
    description=(
        "Backend para consolidação de carteira e análise financeira "
        "integrado à Pluggy.ai. Stack 100% gratuita e open-source."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permitir acesso do Streamlit (localhost:8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Streamlit dev
        "http://127.0.0.1:8501",
        "http://localhost:3000",   # Frontend futuro
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rotas
app.include_router(api_router)


# =====================================================================
# Health check
# =====================================================================

@app.get("/health", tags=["System"])
def health_check():
    """Verifica se o backend está rodando."""
    return {
        "status": "healthy",
        "app": "ValuaçãoBR Backend",
        "version": "1.0.0",
    }
